"""Runtime configuration for local ADK/Gemini execution.

This module loads local environment variables from the project `.env` file.
The `.env` file is intentionally git-ignored and must never be committed.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=False)

_PLACEHOLDER_VALUES = {
    "",
    "your_gemini_api_key_here",
    "your_google_api_key_here",
}


def _is_real_value(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in _PLACEHOLDER_VALUES


_google_api_key = os.getenv("GOOGLE_API_KEY")
_gemini_api_key = os.getenv("GEMINI_API_KEY")
API_KEY_SOURCE: str | None = None

if _is_real_value(_google_api_key):
    API_KEY_SOURCE = "GOOGLE_API_KEY"
elif _is_real_value(_gemini_api_key):
    # Some Google SDK/ADK paths expect GOOGLE_API_KEY. Keep the user's local
    # GEMINI_API_KEY as the source of truth and normalize it only in this process.
    os.environ["GOOGLE_API_KEY"] = _gemini_api_key.strip()
    os.environ.pop("GEMINI_API_KEY", None)
    API_KEY_SOURCE = "GEMINI_API_KEY"


def has_local_api_key() -> bool:
    """Return True when a non-placeholder Gemini/Google API key is configured."""
    return API_KEY_SOURCE is not None
