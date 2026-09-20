"""RubaiSTT v2 client: use a separately hosted Uzbek ASR service.

Never load the 3 GB model in the Render Free bot process.
Never log raw audio, bearer tokens, or full authorization headers.
"""
import os
from urllib.parse import urlsplit
import httpx

class RubaiUnavailable(ValueError):
    pass

def rubai_ready():
    return bool(os.getenv("RUBAI_ASR_URL", "").strip() and
                os.getenv("RUBAI_ASR_TOKEN", "").strip())

def checked_endpoint(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise RubaiUnavailable("RubaiSTT сервер манзили нотўғри: HTTPS манзил керак.")
    if parts.path not in ("", "/"):
        raise RubaiUnavailable("RubaiSTT сервер манзили асосий HTTPS манзил бўлиши керак.")
    return url.rstrip("/") + "/transcribe"

async def rubai_transcribe(audio: bytes, filename="voice.ogg"):
    url = os.getenv("RUBAI_ASR_URL", "").strip()
    token = os.getenv("RUBAI_ASR_TOKEN", "").strip()
    if not url or not token:
        raise RubaiUnavailable("RubaiSTT сервери ҳали уланмаган.")
    if not audio or len(audio) > 10_000_000:
        raise RubaiUnavailable("Овозли хабар 10 МБдан кичик бўлиши керак.")
    endpoint = checked_endpoint(url)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0), follow_redirects=False) as client:
            res = await client.post(endpoint,
                headers={"Authorization": "Bearer " + token},
                files={"file": (filename, audio, "audio/ogg")})
            res.raise_for_status()
            data = res.json()
    except (httpx.HTTPError, ValueError):
        raise RubaiUnavailable("RubaiSTT сервери жавоб бермади. Овозли хабарни кейинроқ юборинг.")
    transcript = data.get("text", "")
    if not isinstance(transcript, str) or not transcript.strip():
        raise RubaiUnavailable("RubaiSTT овозни тушунмади. Қайта айтиб кўринг.")
    return transcript.strip()
