"""Private RubaiSTT v2 transcription microservice.

Run only on a separate computer with enough RAM / GPU; not on Render Free.
HTTPS must be supplied by a reverse proxy or secure tunnel.
"""
import io
import os
import secrets
import subprocess
from contextlib import asynccontextmanager

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from transformers import WhisperForConditionalGeneration, WhisperProcessor

MODEL_ID = "islomov/rubaistt_v2_medium"
MAX_BYTES = 10_000_000
MAX_SECONDS = 30
device = "cuda" if torch.cuda.is_available() else "cpu"
processor = None
model = None

@asynccontextmanager
async def lifespan(app):
    global processor, model
    if not os.environ.get("RUBAI_ASR_TOKEN"):
        raise RuntimeError("RUBAI_ASR_TOKEN is required before starting server")
    processor = WhisperProcessor.from_pretrained(MODEL_ID)
    model = WhisperForConditionalGeneration.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    ).to(device).eval()
    yield

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

@app.get("/health")
def health():
    if model is None:
        raise HTTPException(503, "Model is loading")
    return {"ready": True, "model": "rubaistt_v2_medium"}

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), authorization: str = Header(default="")):
    expected = "Bearer " + os.environ["RUBAI_ASR_TOKEN"]
    if not secrets.compare_digest(authorization, expected):
        raise HTTPException(401, "Unauthorized")
    audio = await file.read(MAX_BYTES + 1)
    if not audio or len(audio) > MAX_BYTES:
        raise HTTPException(413, "Audio missing or too large")
    try:
        # Telegram OGG/Opus is decoded to 16 kHz mono; do not run shell commands.
        converted = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-i", "pipe:0",
             "-t", "31", "-ar", "16000", "-ac", "1", "-f", "wav", "pipe:1"],
            input=audio, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=25, check=True,
        ).stdout
        waveform, sample_rate = sf.read(io.BytesIO(converted), dtype="float32")
    except (subprocess.SubprocessError, ValueError, RuntimeError):
        raise HTTPException(422, "Unsupported or corrupt audio")
    if sample_rate != 16000 or not 0 < len(waveform) <= MAX_SECONDS * 16000:
        raise HTTPException(422, "Audio must be 30 seconds or shorter")
    try:
        features = processor(waveform, sampling_rate=16000, return_tensors="pt").input_features
        features = features.to(device=device, dtype=torch.float16 if device == "cuda" else torch.float32)
        with torch.inference_mode():
            predicted = model.generate(features, language="uz", task="transcribe", max_new_tokens=128)
        recognized = processor.batch_decode(predicted, skip_special_tokens=True)[0].strip()
    except Exception:
        raise HTTPException(503, "Speech recognition unavailable")
    return {"text": recognized, "model": "rubaistt_v2_medium"}
