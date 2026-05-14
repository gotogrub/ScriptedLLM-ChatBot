from pathlib import Path
import json

from chatbot.catalog import CatalogClassifier


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


class DataRepository:
    def __init__(self, settings):
        self.settings = settings
        self.employees = load_json(settings.data_dir / "employees.json")
        self.knowledge = load_json(settings.data_dir / "knowledge.json")
        self.catalog = CatalogClassifier(settings.data_dir / "catalog.reg")

    def get_employee_by_user_id(self, user_id):
        for employee in self.employees:
            if employee.get("user_id") == user_id:
                return employee
        for employee in self.employees:
            if employee.get("user_id") == "demo":
                return employee
        return self.employees[0] if self.employees else None

    def find_employee(self, text):
        normalized = text.lower()
        for employee in self.employees:
            name = employee["name"].lower()
            parts = [part for part in name.split() if len(part) > 2]
            if name in normalized:
                return employee
            if len(parts) >= 2 and parts[0] in normalized and parts[1] in normalized:
                return employee
        return None

    def employee_context(self):
        rows = []
        for employee in self.employees:
            rows.append(
                f"{employee['name']}, {employee['department']}, руководитель {employee['manager']}"
            )
        return "\n".join(rows)

    def documents(self):
        docs = list(self.knowledge.get("documents", []))
        docs.extend(self.catalog.documents())
        for office in self.knowledge.get("offices", []):
            docs.append(
                {
                    "id": f"office_{office['id']}",
                    "title": f"Офис {office['name']}",
                    "category": "offices",
                    "source": office["source"],
                    "text": f"{office['name']}. Адрес: {office['address']}. Получатель: {office['contact']}.",
                    "facts": [office["name"], office["address"], office["contact"]],
                    "forbidden_claims": [],
                }
            )
        docs.append(
            {
                "id": "employees_generated",
                "title": "Справочник сотрудников",
                "category": "employees",
                "source": "employees",
                "text": self.employee_context(),
                "facts": [employee["name"] for employee in self.employees],
                "forbidden_claims": [],
            }
        )
        return docs

    def classify_catalog_items(self, text):
        return self.catalog.classify(text)

    def forbidden_claims(self):
        claims = []
        for document in self.documents():
            claims.extend(document.get("forbidden_claims", []))
        return claims

    def allowed_numbers(self):
        numbers = set()
        for document in self.documents():
            for char_group in document.get("text", "").replace("-", " ").split():
                digits = "".join(char for char in char_group if char.isdigit())
                if digits:
                    numbers.add(digits)
        numbers.update(["2026", "2027", "2028"])
        return sorted(numbers)
