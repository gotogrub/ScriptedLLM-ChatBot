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
    database_path = Path(env_value("DATABASE_PATH", root / "var" / "chatbot.sqlite"))
    if not database_path.is_absolute():
        database_path = root / database_path
    return Settings(
        project_root=root,
        data_dir=Path(env_value("DATA_DIR", root / "data")),
        static_dir=Path(env_value("STATIC_DIR", root / "static")),
        database_path=database_path,
        llm_provider=env_value("LLM_PROVIDER", "ollama").strip().lower(),
        llm_model=env_value("LLM_MODEL", "qwen2.5:7b"),
        llm_base_url=env_value("LLM_BASE_URL", "http://localhost:11434"),
        llm_api_key=env_value("LLM_API_KEY", ""),
        llm_temperature=float(env_value("LLM_TEMPERATURE", "0.1")),
        llm_top_p=float(env_value("LLM_TOP_P", "0.8")),
        llm_top_k=int(env_value("LLM_TOP_K", "30")),
        llm_num_ctx=int(env_value("LLM_NUM_CTX", "4096")),
        llm_timeout=int(env_value("LLM_TIMEOUT", "30")),
        rag_top_k=int(env_value("RAG_TOP_K", "4")),
        host=env_value("HOST", "127.0.0.1"),
        port=int(env_value("PORT", "8081")),
    )


def env_value(name, default):
    return os.environ.get(f"CHATBOT_{name}", os.environ.get(f"AHO_{name}", default))
