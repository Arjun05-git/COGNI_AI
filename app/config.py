from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - keeps setup_database.py runnable before dependency install
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT_DIR / ".env"

load_dotenv(ENV_FILE)


@dataclass(frozen=True)
class Settings:
    app_name: str = "Clinic NL2SQL API"
    app_version: str = "1.0.0"
    llm_provider: str = os.getenv("VANNA_LLM_PROVIDER", "gemini").strip().lower()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    database_path: Path = Path(os.getenv("SQLITE_DB_PATH", str(ROOT_DIR / "clinic.db")))
    memory_seed_path: Path = ROOT_DIR / "app" / "data" / "memory_seed.json"
    max_question_length: int = 500
    memory_max_items: int = 1000

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"


settings = Settings()
