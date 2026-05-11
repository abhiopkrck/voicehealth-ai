"""
core/config.py
Loads all API keys and settings from .env
Import this anywhere: from core.config import settings
"""

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Search
    SERPER_API_KEY: str

    # LLMs
    GEMINI_API_KEY: str  # Removed the hardcoded string!
    GROQ_API_KEY: str    # <-- Added your Groq key here

    # TTS
    SARVAM_API_KEY: str

    # App
    DEFAULT_LOCATION: str = "Pune"
    DEFAULT_LANGUAGE: str = "hi"
    MAX_AUDIO_SIZE_MB: int = 10
    SEARCH_TIME_FILTER: str = "qdr:m3"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()