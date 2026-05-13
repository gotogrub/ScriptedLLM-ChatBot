from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aho_bot.config import Settings
from aho_bot.service import AhoBotService


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
        return AhoBotService(settings)

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


if __name__ == "__main__":
    unittest.main()
