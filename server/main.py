import asyncio
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RUNNER_API_KEY = os.environ["RUNNER_API_KEY"]
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


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


async def run_copilot(text: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "gh", "copilot", "suggest", "-t", "shell", text,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().strip()


@app.get("/health")
async def health():
    return {"status": "ok"}


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
        result = await run_copilot(req.text)
        await send_telegram(req.chat_id, result or "(no output)")
    except Exception as e:
        await send_telegram(req.chat_id, f"Error: {e}")
