from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aho_bot.config import Settings
from aho_bot.data import DataRepository
from aho_bot.rag import RagRetriever
from aho_bot.scripted_validator import ScriptedLLMValidator


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
                citations=[type("Citation", (), {"source": "KB-AHO-001"})()],
            )
            self.assertFalse(result.valid)


if __name__ == "__main__":
    unittest.main()

