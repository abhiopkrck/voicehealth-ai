"""
api/routes/audio.py
Main endpoint: receives audio + location, runs the full agent pipeline, returns audio response.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from agents.intake_agent import intake_agent
from agents.guardrail_agent import guardrail_agent
from agents.research_agent import research_agent
from agents.synthesis_agent import synthesis_agent
from agents.tts_agent import tts_agent
from core.utils import build_error_response, build_success_response

router = APIRouter(prefix="/audio", tags=["audio"])

@router.post("/advise")
async def advise(
    audio: UploadFile = File(...),
    location: str = Form(default="Pune"),
):
    """
    Full pipeline endpoint.
    Accepts: audio file + location string
    Returns: { success, text, audio (base64), source_priority, source_label }
    """
    audio_bytes = await audio.read()

    # ── Agent 1: Transcribe ──
    try:
        intake = await intake_agent(audio_bytes, audio.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intake agent failed: {e}")

    english_text = intake["english_text"]
    detected_lang = intake["detected_language"]
    print(f"🎙️ WHISPER HEARD: {english_text}")
    # ── Agent 2: Guardrail ──
    try:
        guard = await guardrail_agent(english_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Guardrail agent failed: {e}")

    if not guard["is_safe"]:
        # Emergency detected — return hardcoded safety response immediately
        try:
            audio_b64 = await tts_agent(guard["emergency_response"], detected_lang)
        except Exception:
            audio_b64 = None
        return {
            "success": True,
            "text": guard["emergency_response"],
            "audio": audio_b64,
            "source_priority": 0,
            "source_label": "Emergency Guardrail",
        }

    # ── Agent 3: Research (parallel P1/P2/P4/P5) ──
    try:
        research = await research_agent(guard["extracted_symptoms"], location)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research agent failed: {e}")

    # ── Agent 4: Synthesize ──
    try:
        advisory_text = await synthesis_agent(
            location=location,
            symptoms=guard["extracted_symptoms"],
            search_data=research["data"],
            target_language=detected_lang,
            research_payload=research  # <--- THIS IS THE MISSING PIECE!
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synthesis agent failed: {e}")

    # ── Agent 5: TTS ──
    try:
        audio_b64 = await tts_agent(advisory_text, detected_lang)
    except Exception as e:
        # TTS failure is non-fatal — return text only
        audio_b64 = None

    return build_success_response(advisory_text, audio_b64, research["source_priority"], research["source_label"])
