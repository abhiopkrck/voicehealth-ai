"""
api/main.py
FastAPI application entrypoint.
Run with: uvicorn api.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.audio import router as audio_router
from api.routes.health import router as health_router

app = FastAPI(
    title="VoiceHealth AI",
    description="Multi-agent voice health advisory system for rural India",
    version="1.0.0",
)

# CORS — allow all origins for hackathon demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(audio_router)
