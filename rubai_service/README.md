# RubaiSTT v2 Medium — private Uzbek ASR service

Model: https://huggingface.co/islomov/rubaistt_v2_medium (Apache-2.0).

The model weights are about 3.06 GB and the standard model has 769M parameters.
**Do not deploy this container on the current Render Free 512 MB instance.**
This service must run on a **separate** host with enough RAM (start with 8 GB or more for CPU testing; a compatible GPU is preferable). Actual resource requirements, performance and uptime depend on hardware and workload. Cloud GPU/CPU hosting may cost money; do not enable any paid plan without explicit approval.

## Running privately on your own computer

Install Docker, then build and run from this folder:

```sh
docker build -t kassir-rubai .
docker run --rm -p 127.0.0.1:8000:8000 -e RUBAI_ASR_TOKEN="choose-a-new-long-random-private-token" -v rubai-models:/models kassir-rubai
```

First start downloads model weights from Hugging Face (multi-GB), so it may take a while and needs plenty of disk space. Audio (max 10 MB / 30 seconds) is decoded with ffmpeg and transcribed in Uzbek; a JSON response includes `text`. Audio is not saved to disk by the server. Use an HTTPS reverse proxy or private authenticated tunnel to make the service accessible to Render; the local HTTP port above is intentionally bound to 127.0.0.1 and cannot be accessed remotely.

## Connecting from AI Kassir

In the existing AI Kassir **Render test service**, set:

- `RUBAI_ASR_URL`: the privately hosted ASR HTTPS base URL (no trailing /transcribe)
- `RUBAI_ASR_TOKEN`: same independent ASR token configured on this model server

These two environment variables must be configured together. If they are absent, the bot continues to use the existing Groq voice recognizer. If Rubai is configured but unreachable, the bot shows a clear error; it must **not silently send private audio to a different provider**. Keep tokens out of GitHub and chat.

`/health` returns ready only after the model has finished loading. Run tests with **synthetic** audio first, check how accurately it handles numbers, locations, names and your specific Uzbek dialect. Never store a recognized monetary operation without the cashier's confirmation.

This package is not a deployed model: adding the files to GitHub alone does not install 3.06 GB weights on an accessible machine. Do not reuse the Hisobchi AI service, database or token.
