import os


class Config:
    DEFAULT_GEMINI_MODEL = "gemini/gemini-2.5-flash"

    @staticmethod
    def require_env(name: str) -> str:
        value = os.getenv(name, "").strip()
        if not value:
            raise RuntimeError(f"Missing required env var: {name}")
        return value

    @staticmethod
    def get_gemini_model() -> str:
        return os.getenv("LEADSYNC_GEMINI_MODEL", Config.DEFAULT_GEMINI_MODEL)

    @staticmethod
    def get_composio_user_id() -> str:
        return os.getenv("COMPOSIO_USER_ID", "default")

    @staticmethod
    def github_enabled() -> bool:
        return os.getenv("ENABLE_GITHUB", "false").lower() == "true"
