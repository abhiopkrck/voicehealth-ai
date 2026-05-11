"""
core/utils.py
Shared helpers used by 2+ agents.
"""

import re

SUPPORTED_LANGUAGES = {"hi": "Hindi", "ta": "Tamil", "en": "English"}

def detect_language(text: str) -> str:
    """Naive language detection — sufficient for hackathon."""
    hindi_range = re.compile(r'[\u0900-\u097F]')
    tamil_range = re.compile(r'[\u0B80-\u0BFF]')
    if hindi_range.search(text):
        return "hi"
    if tamil_range.search(text):
        return "ta"
    return "en"

def build_error_response(message: str) -> dict:
    return {"success": False, "error": message, "audio": None, "text": None}

def build_success_response(text: str, audio_b64: str, source_priority: int, source_label: str) -> dict:
    return {
        "success": True,
        "text": text,
        "audio": audio_b64,
        "source_priority": source_priority,
        "source_label": source_label,
    }
