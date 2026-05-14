from dataclasses import dataclass, field
import re

from chatbot.domain import REQUEST_SPECS
from chatbot.schemas import ValidationOutcome


@dataclass
class LocalScriptedResult:
    valid: bool
    response: str
    violations: list[str] = field(default_factory=list)


class LocalOutputValidator:
    def __init__(self, constraints=None):
        self.constraints = constraints or []

    def validate(self, response, knowledge_base, current_state, allowed_facts=None):
        violations = []
        violations.extend(self.check_missing_fields(response, current_state))
        violations.extend(self.check_completion_claim(response, current_state))
        violations.extend(self.check_prices(response, knowledge_base))
        violations.extend(self.check_forbidden_claims(response, knowledge_base))
        if violations:
            return LocalScriptedResult(False, "", violations)
        return LocalScriptedResult(True, response, [])

    def check_missing_fields(self, response, current_state):
        if "ask_follow_up_when_required_fields_missing" not in self.constraints:
            return []
        missing = state_value(current_state, "missing_fields", [])
        if not missing:
            return []
        value = response.lower()
        if "?" in response or any(word in value for word in ["уточните", "напишите", "укажите", "выберите"]):
            return []
        return ["При незаполненных полях нужен уточняющий вопрос"]

    def check_completion_claim(self, response, current_state):
        if "do_not_claim_completion_before_ticket_status_created" not in self.constraints:
            return []
        status = state_value(current_state, "status", "")
        value = response.lower()
        if status != "ticket_created" and any(phrase in value for phrase in ["заявка создана", "заявка оформлена"]):
            return ["Нельзя заявлять о создании заявки до статуса created"]
        return []

    def check_prices(self, response, knowledge_base):
        violations = []
        kb_numbers = set()
        for product in knowledge_base.get("products", []):
            if "price" in product:
                kb_numbers.add(str(product["price"]))
        for value in knowledge_base.get("delivery", {}).values():
            for number in re.findall(r"\d+", str(value)):
                kb_numbers.add(number)
        for number in re.findall(r"\b\d{4,}\b", response):
            if number not in kb_numbers:
                violations.append(f"Число {number} отсутствует в базе знаний")
        return violations

    def check_forbidden_claims(self, response, knowledge_base):
        violations = []
        for product in knowledge_base.get("products", []):
            for claim in product.get("forbidden_claims", []):
                if isinstance(claim, str) and contains_forbidden_claim(response, claim):
                    violations.append(f"Запрещенное утверждение: {claim}")
        return violations


def contains_forbidden_claim(response, claim):
    text = response.lower().replace("ё", "е")
    normalized = claim.lower().replace("ё", "е")
    if normalized in text:
        return True
    if len(normalized) > 4 and normalized[-1] in "аяоыеий":
        return normalized[:-1] in text
    return False


def state_value(current_state, key, default=None):
    if isinstance(current_state, dict):
        return current_state.get(key, default)
    return default


def import_output_validator():
    try:
        from scriptedllm.core.validator import OutputValidator
        return OutputValidator
    except Exception:
        return LocalOutputValidator


class ScriptedLLMValidator:
    def __init__(self, repository):
        output_validator = import_output_validator()
        self.repository = repository
        self.constraints = [
            "answer_only_with_allowed_facts",
            "ask_follow_up_when_required_fields_missing",
            "do_not_claim_completion_before_ticket_status_created",
        ]
        self.output_validator = output_validator(self.constraints)
        self.knowledge_base = self.build_scripted_knowledge_base()

    def build_scripted_knowledge_base(self):
        products = []
        for number in self.repository.allowed_numbers():
            products.append({"name": f"approved_number_{number}", "price": number, "forbidden_claims": []})
        for claim in self.repository.forbidden_claims():
            products.append({"name": claim, "forbidden_claims": [claim]})
        delivery = {"approved": " ".join(self.repository.allowed_numbers())}
        return {"products": products, "delivery": delivery}

    def validate_response(self, response, request_type, citations=None, missing_fields=None, state=None):
        citations = citations or []
        allowed = REQUEST_SPECS.get(request_type or "", {}).get("allowed_categories", [])
        current_state = {
            "request_type": request_type or "idle",
            "missing_fields": missing_fields or [],
            "status": state or "idle",
        }
        try:
            scripted = self.output_validator.validate(response, self.knowledge_base, current_state, allowed)
        except Exception:
            scripted = LocalOutputValidator(self.constraints).validate(response, self.knowledge_base, current_state, allowed)
        if not scripted.valid:
            return ValidationOutcome(False, list(scripted.violations))
        forbidden = []
        for claim in self.repository.forbidden_claims():
            if contains_forbidden_claim(response, claim):
                forbidden.append(f"Ответ содержит запрещенное утверждение: {claim}")
        if forbidden:
            return ValidationOutcome(False, forbidden)
        if request_type and not citations:
            return ValidationOutcome(False, ["Ответ по сценарию должен иметь источник из базы знаний"])
        return ValidationOutcome(True, [])

    def validate_ticket(self, ticket):
        request_type = ticket.get("type")
        if request_type not in REQUEST_SPECS:
            return ValidationOutcome(False, ["Неизвестный тип заявки"])
        violations = []
        payload = ticket.get("payload", {})
        for field in REQUEST_SPECS[request_type]["required_fields"]:
            if field == "item_quantities":
                items = payload.get("items") or []
                if not items or any(not item.get("quantity") for item in items):
                    violations.append("Не заполнено количество для позиций")
                continue
            if field not in payload or payload[field] in [None, "", []]:
                violations.append(f"Не заполнено поле {field}")
        if request_type == "sim_card" and not isinstance(payload.get("roaming"), bool):
            violations.append("Поле roaming должно быть boolean")
        if request_type == "business_trip" and not isinstance(payload.get("transfer_needed"), bool):
            violations.append("Поле transfer_needed должно быть boolean")
        if violations:
            return ValidationOutcome(False, violations)
        return ValidationOutcome(True, [])
