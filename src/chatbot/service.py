from datetime import datetime, timezone
import hashlib
import json
import re

from chatbot.config import load_settings
from chatbot.data import DataRepository
from chatbot.domain import FIELD_LABELS, REQUEST_SPECS, SCENARIO_CHOICES
from chatbot.entities import (
    extract_delivery_priority,
    extract_entities,
    extract_office,
    is_remove_items_request,
    should_replace_items,
)
from chatbot.intents import classify_control, classify_request_type, is_capability_question, is_procurement_capability_question
from chatbot.llm import LLMClient
from chatbot.rag import RagRetriever
from chatbot.schemas import ChatResult, to_plain
from chatbot.scripted_validator import ScriptedLLMValidator
from chatbot.storage import ChatStorage
from chatbot.workflow import ConversationWorkflow


class ChatbotService:
    def __init__(self, settings=None):
        self.settings = settings or load_settings()
        self.repository = DataRepository(self.settings)
        self.storage = ChatStorage(self.settings.database_path)
        self.retriever = RagRetriever(self.repository.documents())
        self.validator = ScriptedLLMValidator(self.repository)
        self.llm = LLMClient(self.settings)
        self.workflow = ConversationWorkflow()

    def handle_message(self, user_id, message, runtime_options=None):
        options = self.llm.runtime_options(runtime_options)
        llm_traces = []
        text = (message or "").strip()
        if not text:
            return self.empty_message(user_id)
        self.storage.add_message(user_id, "user", text)
        session = self.storage.load_session(user_id)
        control = classify_control(text)
        if is_capability_question(text):
            result = self.capability_result(user_id, text, options, session)
            self.storage.add_message(user_id, "assistant", result.answer)
            return result
        if control == "status":
            result = self.status_result(user_id)
            self.storage.add_message(user_id, "assistant", result.answer)
            return result
        if control == "cancel" and self.cancel_contains_replacement(text, session):
            llm_traces.append(self.reset_trace(session, text))
            self.storage.reset_session(user_id)
            session = self.storage.load_session(user_id)
            control = None
        if control == "cancel":
            self.storage.reset_session(user_id)
            result = ChatResult(
                user_id=user_id,
                answer="Черновик сброшен. Напишите, какую заявку нужно оформить.",
                state="idle",
                intent="cancel",
                quick_replies=[label for _, label in SCENARIO_CHOICES],
            )
            self.storage.add_message(user_id, "assistant", result.answer)
            return result
        if session.get("request_type") and control == "confirm":
            result = self.confirm_ticket(user_id, session, options)
            self.storage.add_message(user_id, "assistant", result.answer)
            return result
        if session.get("request_type") and control == "edit":
            session["state"] = "collecting"
            self.storage.save_session(session)
            result = ChatResult(
                user_id=user_id,
                answer="Напишите новое значение для поля, которое нужно изменить.",
                state="collecting",
                intent="edit",
                request_type=session["request_type"],
                draft=session.get("draft", {}),
            )
            self.storage.add_message(user_id, "assistant", result.answer)
            return result
        turn = self.interpret_turn(text, session, options)
        if turn.get("trace"):
            llm_traces.append(turn["trace"])
        if self.should_answer_with_knowledge(text, session, turn):
            result = self.knowledge_result(user_id, text, options, session, extra_traces=llm_traces)
            self.storage.add_message(user_id, "assistant", result.answer)
            return result
        request_type = session.get("request_type") or classify_request_type(text)
        catalog_items = self.repository.classify_catalog_items(text)
        if not request_type and catalog_items and turn.get("action") not in ["knowledge_question", "unknown"]:
            request_type = "stationery_order"
        if not request_type:
            if self.looks_like_procurement_request(text):
                result = self.knowledge_result(
                    user_id,
                    text,
                    options,
                    session,
                    force_procurement=True,
                    extra_traces=llm_traces,
                )
            else:
                result = self.unknown_intent(user_id)
            self.storage.add_message(user_id, "assistant", result.answer)
            return result
        if not session.get("request_type"):
            session["request_type"] = request_type
            session["draft"] = {}
        previous_draft = session.get("draft", {})
        entity_text = self.entity_text(text, turn)
        updates = extract_entities(request_type, entity_text, self.repository, user_id, previous_draft, turn.get("action"))
        has_progress = self.has_progress(previous_draft, updates)
        session["draft"] = self.merge_draft(previous_draft, updates)
        missing = self.missing_fields(request_type, session["draft"])
        field = missing[0] if missing else None
        citations = self.retrieve_citations(entity_text, request_type, options, field, session["draft"])
        session["state"] = self.workflow.next_state(missing)
        if missing:
            attempts = self.register_missing_attempt(session, missing[0], has_progress)
            quick_replies = REQUEST_SPECS[request_type].get("quick_replies", {}).get(missing[0], [])
            if attempts >= 2:
                answer = self.helpless_answer(request_type, missing[0])
                intent = "needs_rephrase"
            else:
                llm_result = self.ask_for_field(request_type, missing[0], citations, options, session["draft"])
                answer = llm_result.text
                llm_traces.append(llm_result.trace)
                intent = request_type
        else:
            session["field_attempts"] = {}
            session["last_missing_field"] = None
            llm_result = self.confirmation_text(request_type, session["draft"], citations, options)
            answer = llm_result.text
            llm_traces.append(llm_result.trace)
            quick_replies = ["Подтвердить", "Изменить", "Отменить"]
            intent = "ready_for_confirmation"
        validation = self.validator.validate_response(answer, request_type, citations, missing, session["state"])
        if not validation.valid:
            answer = "Не могу отдать этот ответ: он не прошел ScriptedLLM-валидацию. Уточните данные по заявке."
            quick_replies = ["Отменить"]
        self.storage.save_session(session)
        result = ChatResult(
            user_id=user_id,
            answer=answer,
            state=session["state"],
            intent=intent,
            request_type=request_type,
            draft=session["draft"],
            missing_fields=missing,
            quick_replies=quick_replies,
            citations=[to_plain(item) for item in citations],
            validated=validation.valid,
            violations=validation.violations,
            debug=self.debug_payload(
                options,
                text,
                request_type,
                missing,
                citations,
                llm_traces,
                validation,
                self.debug_history(user_id, answer),
            ),
        )
        self.storage.add_message(user_id, "assistant", result.answer)
        return result

    def empty_message(self, user_id):
        return ChatResult(
            user_id=user_id,
            answer="Напишите запрос по АХО: заказ, SIM-карта, командировка, парковка, такси или Непорядок.",
            state="idle",
            intent="empty",
            quick_replies=[label for _, label in SCENARIO_CHOICES],
        )

    def unknown_intent(self, user_id):
        return ChatResult(
            user_id=user_id,
            answer="Я могу помочь с заявками АХО. Выберите сценарий или опишите запрос другими словами.",
            state="idle",
            intent="unknown",
            quick_replies=[label for _, label in SCENARIO_CHOICES],
        )

    def status_result(self, user_id):
        tickets = self.storage.list_tickets(user_id)
        if not tickets:
            answer = "У вас пока нет созданных заявок."
        else:
            rows = []
            for ticket in tickets[:5]:
                title = REQUEST_SPECS.get(ticket["type"], {}).get("title", ticket["type"])
                rows.append(f"{ticket['id']}: {title}, статус {ticket['status']}")
            answer = "Последние заявки:\n" + "\n".join(rows)
        return ChatResult(user_id=user_id, answer=answer, state="status", intent="status")

    def cancel_contains_replacement(self, text, session):
        if not session.get("request_type"):
            return False
        if not self.repository.classify_catalog_items(text):
            return False
        value = text.lower().replace("ё", "е")
        markers = ["перепутал", "перепутала", "ошибка", "ошибся", "ошиблась", "хочу", "а "]
        return any(marker in value for marker in markers)

    def reset_trace(self, session, text):
        return {
            "purpose": "session_reset",
            "status": "applied",
            "reason": "cancel with replacement item",
            "message": text,
            "previous_request_type": session.get("request_type"),
            "previous_draft": session.get("draft", {}),
        }

    def interpret_turn(self, text, session, options):
        fallback = self.turn_fallback(text, session)
        request_type = session.get("request_type")
        missing = self.missing_fields(request_type, session.get("draft", {})) if request_type else []
        context = {
            "request_type": request_type,
            "state": session.get("state", "idle"),
            "missing_fields": missing,
            "draft": session.get("draft", {}),
            "catalog_items": self.catalog_item_names(),
            "fallback": fallback,
        }
        turn = self.llm.classify_turn(text, context, options)
        return self.guard_turn(turn, fallback, text, session)

    def guard_turn(self, turn, fallback, text, session):
        guarded = None
        catalog_items = self.repository.classify_catalog_items(text)
        draft_items = session.get("draft", {}).get("items") or []
        action = turn.get("action")
        if action == "replace_items" and not draft_items:
            guarded = {"action": "order", "confidence": fallback.get("confidence", 0.75), "reason": "no draft to replace"}
        if action == "remove_items" and not draft_items:
            guarded = dict(fallback)
            guarded["reason"] = "no draft to remove from"
        if action in ["replace_items", "remove_items"] and not catalog_items:
            guarded = dict(fallback)
        if action == "order" and not catalog_items and not self.is_expected_field_answer(text, session):
            guarded = dict(fallback)
        if guarded:
            turn.update(guarded)
            trace = turn.get("trace")
            if trace:
                trace["guarded_classification"] = trace.get("classification")
                trace["classification"] = {key: value for key, value in guarded.items() if key in ["action", "confidence", "reason"]}
                trace["guarded_reason"] = guarded.get("reason")
        return turn

    def turn_fallback(self, text, session):
        request_type = session.get("request_type")
        draft = session.get("draft", {})
        missing = self.missing_fields(request_type, draft) if request_type else []
        catalog_items = self.repository.classify_catalog_items(text)
        if is_remove_items_request(text):
            return {"action": "remove_items", "confidence": 0.9, "reason": "remove marker"}
        if self.local_knowledge_question(text, session):
            return {"action": "knowledge_question", "confidence": 0.85, "reason": "knowledge marker"}
        if catalog_items:
            if should_replace_items(text, draft):
                return {"action": "replace_items", "confidence": 0.9, "reason": "correction marker"}
            if not request_type or self.catalog_text_is_order(text, missing):
                return {"action": "order", "confidence": 0.75, "reason": "catalog item"}
            return {"action": "unknown", "confidence": 0.55, "reason": "catalog mention without order intent"}
        if self.is_expected_field_answer(text, session):
            return {"action": "order", "confidence": 0.8, "reason": "expected field answer"}
        if self.looks_like_procurement_request(text):
            return {"action": "unknown", "confidence": 0.65, "reason": "unsupported procurement item"}
        return {"action": "unknown", "confidence": 0.5, "reason": "no known intent"}

    def catalog_text_is_order(self, text, missing):
        value = text.lower().replace("ё", "е")
        markers = [
            "заказ",
            "закаж",
            "куп",
            "нуж",
            "надо",
            "хочу",
            "добав",
            "еще",
            "ещё",
            "пожалуйста",
        ]
        if any(marker in value for marker in markers):
            return True
        return missing and missing[0] in ["items", "item_quantities"]

    def local_knowledge_question(self, text, session):
        value = text.lower().replace("ё", "е")
        if any(marker in value for marker in ["расскажи", "что-нибудь", "что нибудь", "информац", "подробнее", "погоди"]):
            return True
        if "офис" in value and any(marker in value for marker in ["как", "куда", "какие", "все", "достав"]):
            return True
        if session.get("request_type") and "?" in text and not any(marker in value for marker in ["срочно", "сегодня", "планово"]):
            return True
        return False

    def should_answer_with_knowledge(self, text, session, turn):
        action = (turn or {}).get("action")
        if action == "knowledge_question":
            return True
        if action == "unknown" and session.get("request_type") and not self.is_expected_field_answer(text, session):
            missing = self.missing_fields(session["request_type"], session.get("draft", {}))
            if missing and missing[0] in ["items", "item_quantities"] and not self.looks_like_procurement_request(text):
                return False
            return True
        return self.local_knowledge_question(text, session) and not self.repository.classify_catalog_items(text)

    def is_expected_field_answer(self, text, session):
        request_type = session.get("request_type")
        if not request_type:
            return False
        missing = self.missing_fields(request_type, session.get("draft", {}))
        if not missing:
            return False
        field = missing[0]
        if request_type == "stationery_order" and field == "office":
            return bool(extract_office(text))
        if request_type == "stationery_order" and field == "delivery_priority":
            return bool(extract_delivery_priority(text))
        if request_type == "stationery_order" and field in ["items", "item_quantities"]:
            return bool(self.repository.classify_catalog_items(text))
        return False

    def catalog_item_names(self):
        return [item.name for item in self.repository.catalog.items]

    def entity_text(self, text, turn):
        if turn.get("action") not in ["replace_items", "order"]:
            return text
        value = text.lower().replace("ё", "е")
        if not any(marker in value for marker in ["перепутал", "перепутала", "ошибка", "ошибся", "ошиблась", "а нет", "не "]):
            return text
        matches = list(re.finditer(r"\bа\s+", value))
        for match in reversed(matches):
            tail = text[match.end():].strip(" ,.")
            if self.repository.classify_catalog_items(tail):
                return tail
        return text

    def looks_like_procurement_request(self, text):
        value = text.lower().replace("ё", "е")
        return any(marker in value for marker in ["заказать", "закажи", "купить", "купи", "нужен", "нужна", "нужно"])

    def knowledge_result(self, user_id, text, options, session, force_procurement=False, extra_traces=None):
        request_type = "stationery_order" if force_procurement else session.get("request_type")
        categories = self.knowledge_categories(text, request_type)
        citations = self.retrieve_mixed_citations(text, categories, options)
        fallback = self.knowledge_fallback(text, request_type, citations, session)
        prompt = (
            "Ответь пользователю по-русски как АХО-ассистент. "
            "Используй только факты из RAG-контекста и не меняй черновик заявки. "
            f"Вопрос пользователя: {text}"
        )
        llm_result = self.llm.compose(prompt, self.facts_text(citations, 1200), fallback, options, "knowledge_answer")
        validation = self.validator.validate_response(llm_result.text, request_type, citations, [], session.get("state", "idle"))
        answer = llm_result.text if validation.valid else fallback
        traces = list(extra_traces or [])
        traces.append(llm_result.trace)
        debug = self.debug_payload(
            options,
            text,
            request_type,
            [],
            citations,
            traces,
            validation,
            self.debug_history(user_id, answer),
        )
        return ChatResult(
            user_id=user_id,
            answer=answer,
            state=session.get("state", "idle"),
            intent="knowledge_answer",
            request_type=request_type,
            draft=session.get("draft", {}),
            citations=[to_plain(item) for item in citations],
            validated=validation.valid,
            violations=validation.violations,
            debug=debug,
        )

    def knowledge_categories(self, text, request_type):
        value = text.lower().replace("ё", "е")
        if request_type == "stationery_order" or any(marker in value for marker in ["заказ", "товар", "коф", "канц", "достав"]):
            return ["procurement", "offices"]
        if "офис" in value or "достав" in value:
            return ["offices", "procurement"]
        return ["procurement", "offices", "sim", "travel", "parking", "taxi", "incidents"]

    def retrieve_mixed_citations(self, text, categories, options):
        limit = self.clamp_int((options or {}).get("rag_top_k", self.settings.rag_top_k), 1, 8)
        query = f"{text} каталог офис доставка регламент заявки АХО"
        results = []
        seen = set()
        per_category = max(1, min(2, limit))
        for category in categories:
            for item in self.retriever.retrieve(query, categories=[category], limit=per_category):
                marker = item.id or item.title
                if marker not in seen:
                    results.append(item)
                    seen.add(marker)
                if len(results) >= limit:
                    return results
        if not results:
            return self.retriever.retrieve(query, limit=limit)
        return results[:limit]

    def knowledge_fallback(self, text, request_type, citations, session):
        if self.looks_like_procurement_request(text) and not self.repository.classify_catalog_items(text):
            return "Не нашел такую позицию в каталоге АХО. Могу помочь с заказом канцтоваров из Комус и продуктов из ВкусВилл."
        if request_type == "stationery_order" or session.get("request_type") == "stationery_order":
            office_rows = [
                f"{office['name']}: {office['address']}"
                for office in self.repository.knowledge.get("offices", [])
            ]
            rows = [self.procurement_catalog_answer(), "Офисы доставки: " + "; ".join(office_rows)]
            if session.get("draft"):
                rows.append("Текущий черновик не меняю.")
            return "\n".join(rows)
        if citations:
            return self.facts_text(citations, 900)
        return "Я могу рассказать про заявки АХО, доступные товары, офисы доставки и правила оформления."

    def merge_draft(self, draft, updates):
        merged = dict(draft)
        replace_items = updates.get("_replace_items", False)
        remove_items = updates.get("_remove_items", [])
        if remove_items:
            merged["items"] = self.remove_items(merged.get("items") or [], remove_items)
        for key, value in updates.items():
            if key.startswith("_"):
                continue
            if value in [None, "", []]:
                continue
            if key == "items" and merged.get("items") and not replace_items:
                merged["items"] = self.merge_items(merged["items"], value)
            else:
                merged[key] = value
        return merged

    def has_progress(self, draft, updates):
        if updates.get("_remove_items") or updates.get("_replace_items"):
            return True
        for key, value in updates.items():
            if value in [None, "", []]:
                continue
            if key.startswith("_"):
                continue
            if key == "items":
                if self.items_have_progress(draft.get("items") or [], value):
                    return True
                continue
            if draft.get(key) != value:
                return True
        return False

    def items_have_progress(self, existing, incoming):
        current = {item.get("url") or item.get("name"): item.get("quantity") for item in existing}
        for item in incoming:
            marker = item.get("url") or item.get("name")
            if marker not in current:
                return True
            if item.get("quantity") and item.get("quantity") != current.get(marker):
                return True
        return False

    def register_missing_attempt(self, session, field, has_progress):
        attempts = session.get("field_attempts") or {}
        if has_progress or session.get("last_missing_field") != field:
            attempts[field] = 0
        else:
            attempts[field] = attempts.get(field, 0) + 1
        session["field_attempts"] = attempts
        session["last_missing_field"] = field
        return attempts[field]

    def helpless_answer(self, request_type, field):
        if request_type == "stationery_order" and field in ["items", "item_quantities"]:
            return "Не смог распознать товар по каталогу. Напишите позицию из каталога или пришлите ссылку на товар."
        if field == "office":
            return "Не смог определить офис. Выберите Центральный офис, Склад или Сервис-центр."
        if field == "delivery_priority":
            return "Не смог определить срочность. Напишите срочно, сегодня или планово."
        return "Не смог уверенно разобрать ответ. Переформулируйте одним сообщением с нужными данными."

    def merge_items(self, existing, incoming):
        result = [dict(item) for item in existing]
        for new_item in incoming:
            marker = new_item.get("url") or new_item.get("name")
            found = False
            for old_item in result:
                old_marker = old_item.get("url") or old_item.get("name")
                if old_marker == marker:
                    if new_item.get("quantity"):
                        old_item["quantity"] = new_item["quantity"]
                    found = True
            if not found:
                result.append(new_item)
        return result

    def remove_items(self, existing, removed):
        markers = {item.get("url") or item.get("name") for item in removed}
        return [item for item in existing if (item.get("url") or item.get("name")) not in markers]

    def missing_fields(self, request_type, draft):
        missing = []
        for field in REQUEST_SPECS[request_type]["required_fields"]:
            if field == "item_quantities":
                items = draft.get("items") or []
                if not items or any(not item.get("quantity") for item in items):
                    missing.append(field)
                continue
            if field not in draft or draft[field] in [None, "", []]:
                missing.append(field)
        return missing

    def capability_result(self, user_id, text, options, session):
        if is_procurement_capability_question(text):
            request_type = "stationery_order"
            citations = self.retrieve_citations(text, request_type, options)
            answer = self.procurement_catalog_answer()
            quick_replies = ["Карандаши 10, линейки 2", "Бумага А4 5 пачек", "Ссылка на товар, 5 штук"]
        else:
            request_type = session.get("request_type")
            citations = self.retriever.retrieve(text + " АХО заявки услуги регламент", limit=4)
            answer = (
                "Я могу оформить заявки АХО: закупки Комус и ВкусВилл, корпоративную SIM-карту, командировку, парковку, такси и Непорядок.\n"
                "Если данных не хватает, я задам уточняющие вопросы и соберу JSON-заявку."
            )
            quick_replies = [label for _, label in SCENARIO_CHOICES]
        return ChatResult(
            user_id=user_id,
            answer=answer,
            state=session.get("state", "idle"),
            intent="capabilities",
            request_type=request_type,
            draft=session.get("draft", {}),
            quick_replies=quick_replies,
            citations=[to_plain(item) for item in citations],
            debug=self.debug_payload(options, text, request_type, [], citations, [], None, self.debug_history(user_id, answer)),
        )

    def procurement_catalog_answer(self):
        rows = []
        for group in self.repository.catalog.groups:
            names = ", ".join(item.name.lower() for item in group.items)
            rows.append(f"{group.label} через {group.supplier}: {names}.")
        rows.append("Напишите позиции и количество, можно также прислать ссылку на товар.")
        return "\n".join(rows)

    def ask_for_field(self, request_type, field, citations, options, draft):
        question = self.follow_up_fallback(request_type, field, draft)
        fallback = question
        facts = self.facts_text(citations, 650)
        prompt = f"Верни один короткий уточняющий вопрос пользователю. Не меняй запрашиваемое поле: {fallback}"
        llm_result = self.llm.compose(prompt, facts, fallback, options, "follow_up")
        return self.guard_follow_up(llm_result, field, fallback)

    def follow_up_fallback(self, request_type, field, draft):
        if request_type == "stationery_order" and field == "item_quantities":
            items = self.item_names(draft)
            if items:
                return f"Понял позиции: {items}. Напишите количество по каждой позиции."
        if request_type == "stationery_order" and field == "office":
            return "В какой офис доставить заказ: Центральный офис, Склад или Сервис-центр?"
        if request_type == "stationery_order" and field == "delivery_priority":
            return "Какая срочность у заказа: срочно, сегодня или планово?"
        return REQUEST_SPECS[request_type]["questions"][field]

    def guard_follow_up(self, llm_result, field, fallback):
        value = llm_result.text.lower()
        use_fallback = False
        if field == "item_quantities":
            use_fallback = ("колич" not in value and "сколько" not in value) or "ссыл" in value
        if field == "items":
            use_fallback = (
                ("что" not in value and "пози" not in value and "товар" not in value)
                or "нужно ли" in value
                or "можете" in value
            )
        if field == "office":
            unsupported_rule = any(word in value for word in ["не используется", "недоступ", "нельзя", "не подходит"])
            use_fallback = unsupported_rule or not all(word in value for word in ["централь", "склад", "сервис"])
        if field == "delivery_priority":
            use_fallback = not all(word in value for word in ["срочно", "сегодня", "план"])
        if use_fallback:
            llm_result.trace["status"] = "guarded_fallback"
            llm_result.trace["guarded_reason"] = f"wrong follow-up for {field}"
            llm_result.trace["fallback"] = fallback
            llm_result.text = fallback
        return llm_result

    def item_names(self, draft):
        items = draft.get("items") or []
        names = [item.get("name") for item in items if item.get("name")]
        return ", ".join(names)

    def confirmation_text(self, request_type, draft, citations, options):
        title = REQUEST_SPECS[request_type]["title"]
        lines = [f"Собрал данные для заявки: {title}.", self.render_draft(request_type, draft)]
        lines.append("Подтвердите создание заявки или напишите, что изменить.")
        fallback = "\n".join(line for line in lines if line)
        return self.llm.compose(
            json.dumps(draft, ensure_ascii=False),
            self.facts_text(citations),
            fallback,
            options,
            "confirmation",
        )

    def confirm_ticket(self, user_id, session, options=None):
        options = self.llm.runtime_options(options)
        request_type = session.get("request_type")
        draft = session.get("draft", {})
        if not request_type:
            return self.unknown_intent(user_id)
        missing = self.missing_fields(request_type, draft)
        field = missing[0] if missing else None
        citations = self.retrieve_citations(json.dumps(draft, ensure_ascii=False), request_type, options, field, draft)
        if missing:
            session["state"] = "collecting"
            self.storage.save_session(session)
            llm_result = self.ask_for_field(request_type, missing[0], citations, options, draft)
            answer = llm_result.text
            return ChatResult(
                user_id=user_id,
                answer=answer,
                state="collecting",
                intent="missing_fields",
                request_type=request_type,
                draft=draft,
                missing_fields=missing,
                quick_replies=REQUEST_SPECS[request_type].get("quick_replies", {}).get(missing[0], []),
                citations=[to_plain(item) for item in citations],
                debug=self.debug_payload(
                    options,
                    "",
                    request_type,
                    missing,
                    citations,
                    [llm_result.trace],
                    None,
                    self.debug_history(user_id, answer),
                ),
            )
        ticket = self.build_ticket(user_id, request_type, draft, citations)
        validation = self.validator.validate_ticket(ticket)
        if not validation.valid:
            return ChatResult(
                user_id=user_id,
                answer="Заявка не создана: данные не прошли валидацию.",
                state="collecting",
                intent="validation_failed",
                request_type=request_type,
                draft=draft,
                violations=validation.violations,
                validated=False,
                debug=self.debug_payload(
                    options,
                    "",
                    request_type,
                    missing,
                    citations,
                    [],
                    validation,
                    self.debug_history(user_id, "Заявка не создана: данные не прошли валидацию."),
                ),
            )
        self.storage.create_ticket(ticket)
        self.storage.reset_session(user_id)
        answer = "Заявка создана.\n" + json.dumps(ticket, ensure_ascii=False, indent=2)
        return ChatResult(
            user_id=user_id,
            answer=answer,
            state="ticket_created",
            intent="confirm",
            request_type=request_type,
            ticket=ticket,
            citations=[to_plain(item) for item in citations],
            debug=self.debug_payload(options, "", request_type, [], citations, [], validation, self.debug_history(user_id, answer)),
        )

    def build_ticket(self, user_id, request_type, draft, citations):
        ticket_id = self.ticket_id(user_id, request_type, draft)
        now = utc_now()
        return {
            "id": ticket_id,
            "type": request_type,
            "service": REQUEST_SPECS[request_type]["service"],
            "user_id": user_id,
            "status": "created",
            "payload": draft,
            "created_at": now,
            "updated_at": now,
        }

    def ticket_id(self, user_id, request_type, draft):
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ"
        seed = f"{user_id}:{request_type}:{json.dumps(draft, ensure_ascii=False, sort_keys=True)}:{utc_now()}"
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        suffix = "".join(alphabet[item % len(alphabet)] for item in digest[:8])
        return f"AHO-{suffix}"

    def retrieve_citations(self, text, request_type, options=None, field=None, draft=None):
        if request_type == "stationery_order" and field == "office":
            return self.retrieve_mixed_citations(text, ["procurement", "offices"], options or {})
        categories = self.retrieval_categories(request_type, field)
        query = f"{text} {REQUEST_SPECS[request_type]['title']}"
        limit = self.clamp_int((options or {}).get("rag_top_k", self.settings.rag_top_k), 1, 8)
        citations = self.retriever.retrieve(query, categories=categories, limit=limit)
        if request_type == "stationery_order" and field is None and draft and draft.get("office"):
            citations = self.only_selected_office(citations, draft["office"], limit)
        return citations

    def only_selected_office(self, citations, office, limit):
        result = []
        office_found = False
        for item in citations:
            if item.category != "offices":
                result.append(item)
                continue
            if office in item.title or office in item.text:
                result.append(item)
                office_found = True
        if not office_found:
            for item in self.retriever.retrieve(office, categories=["offices"], limit=3):
                if office in item.title or office in item.text:
                    result.append(item)
                    break
        return result[:limit]

    def retrieval_categories(self, request_type, field=None):
        if request_type == "stationery_order":
            if field in ["items", "item_quantities", "delivery_priority"]:
                return ["procurement"]
            if field == "office":
                return ["offices"]
            return ["procurement", "offices"]
        return [category for category in REQUEST_SPECS[request_type]["allowed_categories"] if category != "employees"]

    def facts_text(self, citations, max_chars=900):
        rows = []
        used = 0
        for item in citations:
            text = f"{item.title}: {item.text}"
            if used + len(text) > max_chars:
                remaining = max_chars - used
                if remaining > 80:
                    rows.append(text[:remaining])
                break
            rows.append(text)
            used += len(text)
        return "\n".join(rows)

    def render_draft(self, request_type, draft):
        lines = []
        for field in REQUEST_SPECS[request_type]["required_fields"]:
            if field == "item_quantities":
                continue
            value = draft.get(field)
            if value in [None, "", []]:
                continue
            label = FIELD_LABELS.get(field, field)
            lines.append(f"{label}: {self.format_value(value)}")
        return "\n".join(lines)

    def format_value(self, value):
        if isinstance(value, bool):
            return "да" if value else "нет"
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, dict):
                    name = item.get("name", "Позиция")
                    quantity = item.get("quantity") or "не указано"
                    url = item.get("url")
                    if url:
                        parts.append(f"{name}, {quantity}, {url}")
                    else:
                        parts.append(f"{name}, {quantity}")
                else:
                    parts.append(str(item))
            return "; ".join(parts)
        return str(value)

    def debug_payload(self, options, user_message, request_type, missing, citations, llm_traces, validation, history=None):
        payload = {
            "created_at": utc_now(),
            "provider": options.get("provider"),
            "model": options.get("model"),
            "base_url": options.get("base_url"),
            "rag": {
                "top_k": self.clamp_int(options.get("rag_top_k", self.settings.rag_top_k), 1, 8),
                "request_type": request_type,
                "missing_fields": missing,
                "chunks": [self.chunk_debug(index, item) for index, item in enumerate(citations, start=1)],
            },
            "llm": llm_traces,
            "history": history or [],
        }
        if user_message:
            payload["message"] = user_message
        if validation:
            payload["validation"] = {
                "valid": validation.valid,
                "violations": validation.violations,
            }
        return payload

    def debug_history(self, user_id, pending_answer=None):
        history = self.storage.recent_messages(user_id, limit=80)
        if pending_answer:
            history.append({"role": "assistant", "content": pending_answer, "created_at": utc_now()})
        return history

    def chunk_debug(self, index, item):
        return {
            "rank": index,
            "id": item.id,
            "title": item.title,
            "category": item.category,
            "reference": item.source,
            "score": item.score,
            "characters": len(item.text),
            "text": item.text,
        }

    def clamp_int(self, value, minimum, maximum):
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = minimum
        return max(minimum, min(maximum, number))


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
