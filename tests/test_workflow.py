from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chatbot.config import Settings
from chatbot.service import ChatbotService


class WorkflowTest(unittest.TestCase):
    def service(self, tmp):
        root = Path(__file__).resolve().parents[1]
        settings = Settings(
            project_root=root,
            data_dir=root / "data",
            static_dir=root / "static",
            database_path=Path(tmp) / "test.sqlite",
            llm_provider="scripted",
            llm_model="",
            llm_base_url="",
            llm_api_key="",
            host="127.0.0.1",
            port=0,
        )
        return ChatbotService(settings)

    def test_stationery_ticket_flow(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            first = service.handle_message("demo", "Нужна бумага А4 5 пачек в центральный офис срочно")
            self.assertEqual(first.state, "ready_for_confirmation")
            self.assertFalse(first.missing_fields)
            second = service.handle_message("demo", "Подтвердить")
            self.assertEqual(second.state, "ticket_created")
            self.assertEqual(second.ticket["type"], "stationery_order")
            self.assertEqual(second.ticket["payload"]["items"][0]["quantity"], 5)

    def test_taxi_ticket_flow(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            first = service.handle_message(
                "demo",
                "Закажи такси из центрального офиса в Шереметьево завтра в 18:00 для 2 человек",
            )
            self.assertEqual(first.state, "ready_for_confirmation")
            second = service.handle_message("demo", "да")
            self.assertEqual(second.ticket["type"], "taxi_order")
            self.assertEqual(second.ticket["payload"]["passengers"], 2)
            self.assertEqual(second.ticket["payload"]["pickup"], "Центральный офис")

    def test_sim_new_employee_asks_name(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            result = service.handle_message("demo", "Оформи номер для нового сотрудника")
            self.assertEqual(result.request_type, "sim_card")
            self.assertIn("employee", result.missing_fields)

    def test_procurement_understands_catalog_items(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            result = service.handle_message("demo", "Я хочу заказать карандаши, молоко и кофе")
            self.assertEqual(result.request_type, "stationery_order")
            self.assertEqual([item["name"] for item in result.draft["items"]], ["Карандаши", "Молоко", "Кофе"])
            self.assertIn("item_quantities", result.missing_fields)

    def test_procurement_catalog_splits_item_categories(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            result = service.handle_message("demo", "Закажи линейки и кофе")
            item_categories = {item["category"] for item in result.draft["items"]}
            citation_titles = {item["title"] for item in result.citations}
            self.assertEqual(item_categories, {"Канцтовары", "Продукты"})
            self.assertIn("Каталог Комус: Канцтовары", citation_titles)
            self.assertIn("Каталог ВкусВилл: Продукты", citation_titles)

    def test_procurement_catalog_regex_handles_coffee_typos(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            for word in ["кофе", "кофей", "кофея", "кофею", "кофек", "кофи", "Кофе"]:
                found = service.repository.classify_catalog_items(f"2 банки {word}")
                self.assertEqual(found[0]["name"], "Кофе")

    def test_procurement_catalog_regex_handles_other_declensions(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            samples = {
                "2 ручки": "Ручки",
                "3 карандашами": "Карандаши",
                "4 линейками": "Линейки",
                "5 салфеток": "Салфетки",
                "6 пачек печенья": "Печенье",
                "7 бутылок воды": "Вода",
            }
            for text, name in samples.items():
                found = service.repository.classify_catalog_items(text)
                self.assertEqual(found[0]["name"], name)

    def test_new_explicit_procurement_request_replaces_stale_items(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            service.handle_message("demo", "Закажи линейки и кофе")
            result = service.handle_message("demo", "Я хочу заказать 10 карандашей и две банки кофе")
            items = {item["name"]: item["quantity"] for item in result.draft["items"]}
            self.assertEqual(items, {"Карандаши": 10, "Кофе": 2})

    def test_procurement_correction_replaces_old_items_and_defaults_single_pack(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            service.handle_message("demo", "Надо 100 штук карандашей")
            result = service.handle_message("demo", "А нет ошибка, хочу две банки кофе и еще пожалуйста упаковку печенья")
            items = {item["name"]: item["quantity"] for item in result.draft["items"]}
            self.assertEqual(items, {"Кофе": 2, "Печенье": 1})

    def test_cancel_with_replacement_resets_old_items_and_extracts_new_item(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            service.handle_message("demo", "Я хочу заказать два карандаша")
            result = service.handle_message("demo", "А нет. отмена, я перепутал, не два карандаша, а две баночки кофия")
            items = {item["name"]: item["quantity"] for item in result.draft["items"]}
            self.assertEqual(items, {"Кофе": 2})
            self.assertEqual(result.intent, "stationery_order")
            self.assertEqual(result.missing_fields, ["office", "delivery_priority"])

    def test_procurement_remove_item_from_draft(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            service.handle_message("demo", "Нужно 10 карандашей, две банки кофе и упаковку печенья")
            result = service.handle_message("demo", "Нет, карандаши убери")
            items = {item["name"]: item["quantity"] for item in result.draft["items"]}
            self.assertEqual(items, {"Кофе": 2, "Печенье": 1})
            self.assertEqual(result.missing_fields, ["office", "delivery_priority"])

    def test_active_procurement_knowledge_question_does_not_change_draft(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            service.handle_message("demo", "Нужно 2 пачки кофе")
            result = service.handle_message("demo", "Расскажи всю информацию в какие офисы и как я могу доставить")
            self.assertEqual(result.intent, "knowledge_answer")
            self.assertEqual(result.draft["items"][0]["name"], "Кофе")
            categories = {item["category"] for item in result.citations}
            self.assertIn("procurement", categories)
            self.assertIn("offices", categories)

    def test_unknown_procurement_item_goes_to_knowledge_answer(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            result = service.handle_message("demo", "Я хочу заказать плюшевого мишку")
            self.assertEqual(result.intent, "knowledge_answer")
            self.assertIn("Не нашел", result.answer)

    def test_debug_trace_contains_message_history(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            result = service.handle_message("demo", "Нужно 2 пачки кофе")
            history = result.debug["history"]
            self.assertGreaterEqual(len(history), 2)
            self.assertEqual(history[-2]["role"], "user")
            self.assertEqual(history[-1]["role"], "assistant")
            self.assertIn("created_at", result.debug)

    def test_llm_pipe_classification_uses_safe_fallback_action(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            result = service.llm.parse_classification(
                '{"action":"order|replace_items","confidence":1.0,"reason":"catalog item"}',
                {"action": "order", "confidence": 0.75, "reason": "catalog item"},
            )
            self.assertEqual(result["action"], "order")

    def test_remove_item_classification_is_guarded_when_draft_is_empty(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            turn = {
                "action": "remove_items",
                "confidence": 0.9,
                "reason": "model saw negation",
                "trace": {"classification": {"action": "remove_items"}},
            }
            result = service.guard_turn(
                turn,
                {"action": "order", "confidence": 0.75, "reason": "catalog item"},
                "не два карандаша, а две баночки кофия",
                {"draft": {}},
            )
            self.assertEqual(result["action"], "order")
            self.assertEqual(result["trace"]["guarded_reason"], "no draft to remove from")

    def test_procurement_continues_after_scenario_button(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            service.handle_message("demo", "Заказ канцтоваров")
            result = service.handle_message("demo", "10 карандашей и 2 линейки")
            items = {item["name"]: item["quantity"] for item in result.draft["items"]}
            self.assertEqual(items["Карандаши"], 10)
            self.assertEqual(items["Линейки"], 2)
            self.assertNotIn("items", result.missing_fields)
            self.assertNotIn("item_quantities", result.missing_fields)

    def test_procurement_rag_does_not_pull_employee_directory_for_items(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            result = service.handle_message("demo", "Заказ канцтоваров")
            categories = {item["category"] for item in result.citations}
            self.assertNotIn("employees", categories)

    def test_procurement_capability_question_does_not_start_draft(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            result = service.handle_message("demo", "А что я могу заказать?")
            self.assertEqual(result.intent, "capabilities")
            self.assertEqual(result.draft, {})
            self.assertIn("карандаши", result.answer.lower())

    def test_procurement_keeps_quantities_near_items(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            result = service.handle_message(
                "demo",
                "Надо срочно пять карандашей, 2 бутылки молока и одну пачку кофи",
            )
            items = {item["name"]: item["quantity"] for item in result.draft["items"]}
            self.assertEqual(items["Карандаши"], 5)
            self.assertEqual(items["Молоко"], 2)
            self.assertEqual(items["Кофе"], 1)
            self.assertEqual(result.draft["delivery_priority"], "Срочно")
            self.assertEqual(result.missing_fields, ["office"])

    def test_office_follow_up_guard_keeps_all_options(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            trace = {"status": "generated"}
            llm_result = type(
                "Result",
                (),
                {"text": "В какой офис доставить заказ: Центральный офис или Сервис-центр?", "trace": trace},
            )()
            guarded = service.guard_follow_up(
                llm_result,
                "office",
                "В какой офис доставить заказ: Центральный офис, Склад или Сервис-центр?",
            )
            self.assertEqual(guarded.trace["status"], "guarded_fallback")
            self.assertIn("Склад", guarded.text)

    def test_office_follow_up_guard_rejects_unsupported_restrictions(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            trace = {"status": "generated"}
            llm_result = type(
                "Result",
                (),
                {
                    "text": "В какой офис доставить заказ: Центральный офис или Склад? Сервис-центр не используется для закупок.",
                    "trace": trace,
                },
            )()
            guarded = service.guard_follow_up(
                llm_result,
                "office",
                "В какой офис доставить заказ: Центральный офис, Склад или Сервис-центр?",
            )
            self.assertEqual(guarded.trace["status"], "guarded_fallback")
            self.assertEqual(guarded.text, "В какой офис доставить заказ: Центральный офис, Склад или Сервис-центр?")

    def test_items_follow_up_guard_rejects_yes_no_question(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            trace = {"status": "generated"}
            llm_result = type(
                "Result",
                (),
                {"text": "Нужно ли вам перечислить товары или отправить ссылки на них?", "trace": trace},
            )()
            guarded = service.guard_follow_up(
                llm_result,
                "items",
                "Напишите, что нужно заказать. Можно перечислить товары или прислать ссылку.",
            )
            self.assertEqual(guarded.trace["status"], "guarded_fallback")
            self.assertEqual(
                guarded.text,
                "Напишите, что нужно заказать. Можно перечислить товары или прислать ссылку.",
            )

    def test_ticket_does_not_expose_internal_sources(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            service.handle_message("demo", "Нужно 10 карандашей и 2 линейки в центральный офис сегодня")
            result = service.handle_message("demo", "Подтвердить")
            self.assertNotIn("sources", result.ticket)
            self.assertNotIn("Источник", result.answer)

    def test_repeated_unrecognized_item_gets_helpless_phrase(self):
        with TemporaryDirectory() as tmp:
            service = self.service(tmp)
            service.handle_message("demo", "Заказ канцтоваров")
            service.handle_message("demo", "гвозди")
            result = service.handle_message("demo", "шурупы")
            self.assertEqual(result.intent, "needs_rephrase")
            self.assertIn("Не смог распознать товар", result.answer)


if __name__ == "__main__":
    unittest.main()
