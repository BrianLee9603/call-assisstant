import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# LLM Configuration
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))

# Ensure Google API key is set
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

# Global Constants (DRY Compliance)
DEFAULT_GREETING = "Thank you for calling Jacobs Plumbing. How can I assist you today?"

# Langfuse Configuration & Placeholder Keys Protection
def _clean_credential(val: str | None) -> str | None:
    if not val:
        return None
    val_clean = val.strip().strip('"').strip("'")
    if (
        not val_clean 
        or val_clean.lower().startswith("your_") 
        or "placeholder" in val_clean.lower()
    ):
        return None
    return val_clean

LANGFUSE_PUBLIC_KEY = _clean_credential(os.getenv("LANGFUSE_PUBLIC_KEY"))
LANGFUSE_SECRET_KEY = _clean_credential(os.getenv("LANGFUSE_SECRET_KEY"))
LANGFUSE_HOST = _clean_credential(os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL")) or "https://cloud.langfuse.com"

def validate_config():
    """Validates that all required environment variables are set."""
    if not GOOGLE_API_KEY:
        print("[WARNING] GOOGLE_API_KEY or GEMINI_API_KEY is not set. The LLM calls will fail.")
        return False
    return True
