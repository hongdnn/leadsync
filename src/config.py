"""Backward-compatible config facade over `src.shared` helpers."""

from src.shared import _required_env, _required_gemini_api_key, build_llm, composio_user_id


class Config:
    """Deprecated shim retained for legacy tests/import paths."""

    DEFAULT_GEMINI_MODEL = "gemini/gemini-2.5-flash"

    @staticmethod
    def require_env(name: str) -> str:
        """Delegate to shared required env helper."""
        return _required_env(name)

    @staticmethod
    def require_gemini_api_key() -> str:
        """Delegate to shared gemini key helper."""
        return _required_gemini_api_key()

    @staticmethod
    def get_gemini_model() -> str:
        """Delegate to shared model selection."""
        return build_llm()

    @staticmethod
    def get_composio_user_id() -> str:
        """Delegate to shared composio user id helper."""
        return composio_user_id()

    @staticmethod
    def github_enabled() -> bool:
        """Legacy feature flag retained for backward compatibility."""
        return False
