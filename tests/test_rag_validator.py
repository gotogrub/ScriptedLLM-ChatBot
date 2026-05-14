from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chatbot.config import Settings
from chatbot.data import DataRepository
from chatbot.rag import RagRetriever
from chatbot.scripted_validator import ScriptedLLMValidator


class RagValidatorTest(unittest.TestCase):
    def settings(self, tmp):
        root = Path(__file__).resolve().parents[1]
        return Settings(
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

    def test_rag_returns_procurement_document(self):
        with TemporaryDirectory() as tmp:
            repository = DataRepository(self.settings(tmp))
            retriever = RagRetriever(repository.documents())
            results = retriever.retrieve("бумага А4 Комус", categories=["procurement"], limit=2)
            self.assertTrue(results)
            self.assertEqual(results[0].category, "procurement")

    def test_validator_rejects_forbidden_claim(self):
        with TemporaryDirectory() as tmp:
            repository = DataRepository(self.settings(tmp))
            validator = ScriptedLLMValidator(repository)
            result = validator.validate_response(
                "Оформлю скидку на заказ канцтоваров.",
                "stationery_order",
                citations=[type("Citation", (), {"source": "policy:procurement"})()],
            )
            self.assertFalse(result.valid)

    def test_validator_requires_follow_up_for_missing_fields(self):
        with TemporaryDirectory() as tmp:
            repository = DataRepository(self.settings(tmp))
            validator = ScriptedLLMValidator(repository)
            result = validator.validate_response(
                "Собрал данные для заявки.",
                "stationery_order",
                citations=[type("Citation", (), {"source": "policy:procurement"})()],
                missing_fields=["items"],
                state="collecting",
            )
            self.assertFalse(result.valid)

    def test_validator_rejects_early_completion_claim(self):
        with TemporaryDirectory() as tmp:
            repository = DataRepository(self.settings(tmp))
            validator = ScriptedLLMValidator(repository)
            result = validator.validate_response(
                "Заявка создана.",
                "stationery_order",
                citations=[type("Citation", (), {"source": "policy:procurement"})()],
                missing_fields=[],
                state="ready_for_confirmation",
            )
            self.assertFalse(result.valid)


if __name__ == "__main__":
    unittest.main()
