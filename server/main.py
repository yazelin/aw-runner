import asyncio
import os
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RUNNER_API_KEY = os.environ["RUNNER_API_KEY"]
COPILOT_GITHUB_TOKEN = os.environ["COPILOT_GITHUB_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)


class TaskRequest(BaseModel):
    text: str
    chat_id: str


async def send_telegram(chat_id: str, text: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )


async def run_copilot(text: str, chat_id: str) -> str:
    prompt = (
        f"{open('prompt.md').read()}\n\n"
        f"## Message\n"
        f"- Chat ID: {chat_id}\n"
        f"- Text: {text}"
    )
    proc = await asyncio.create_subprocess_exec(
        "copilot", "--autopilot", "--yolo", "-p", prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "COPILOT_GITHUB_TOKEN": COPILOT_GITHUB_TOKEN},
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().strip()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status")
async def status():
    elapsed = int(time.time() - START_TIME)
    hours, rem = divmod(elapsed, 3600)
    minutes, seconds = divmod(rem, 60)
    return {
        "status": "ok",
        "uptime_seconds": elapsed,
        "uptime": f"{hours}h {minutes}m {seconds}s",
    }


@app.post("/task")
async def task(
    req: TaskRequest,
    x_api_key: str = Header(...),
):
    if x_api_key != RUNNER_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    asyncio.create_task(_process(req))
    return {"status": "accepted"}


async def _process(req: TaskRequest) -> None:
    try:
        await run_copilot(req.text, req.chat_id)
        # Copilot sends the reply itself via .github/scripts/send_telegram_message.py
    except Exception as e:
        await send_telegram(req.chat_id, f"Error: {e}")
