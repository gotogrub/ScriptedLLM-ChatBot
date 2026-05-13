from dataclasses import dataclass
from pathlib import Path
import os


@dataclass
class Settings:
    project_root: Path
    data_dir: Path
    static_dir: Path
    database_path: Path
    llm_provider: str
    llm_model: str
    llm_base_url: str
    llm_api_key: str
    host: str
    port: int
    llm_temperature: float = 0.1
    llm_top_p: float = 0.8
    llm_top_k: int = 30
    llm_num_ctx: int = 4096
    llm_timeout: int = 30
    rag_top_k: int = 4


def default_project_root():
    return Path(__file__).resolve().parents[2]


def load_settings():
    root = default_project_root()
    database_path = Path(os.environ.get("AHO_DATABASE_PATH", root / "var" / "aho_bot.sqlite"))
    if not database_path.is_absolute():
        database_path = root / database_path
    return Settings(
        project_root=root,
        data_dir=Path(os.environ.get("AHO_DATA_DIR", root / "data")),
        static_dir=Path(os.environ.get("AHO_STATIC_DIR", root / "static")),
        database_path=database_path,
        llm_provider=os.environ.get("AHO_LLM_PROVIDER", "ollama").strip().lower(),
        llm_model=os.environ.get("AHO_LLM_MODEL", "qwen2.5:7b"),
        llm_base_url=os.environ.get("AHO_LLM_BASE_URL", "http://localhost:11434"),
        llm_api_key=os.environ.get("AHO_LLM_API_KEY", ""),
        llm_temperature=float(os.environ.get("AHO_LLM_TEMPERATURE", "0.1")),
        llm_top_p=float(os.environ.get("AHO_LLM_TOP_P", "0.8")),
        llm_top_k=int(os.environ.get("AHO_LLM_TOP_K", "30")),
        llm_num_ctx=int(os.environ.get("AHO_LLM_NUM_CTX", "4096")),
        llm_timeout=int(os.environ.get("AHO_LLM_TIMEOUT", "30")),
        rag_top_k=int(os.environ.get("AHO_RAG_TOP_K", "4")),
        host=os.environ.get("AHO_HOST", "127.0.0.1"),
        port=int(os.environ.get("AHO_PORT", "8081")),
    )
