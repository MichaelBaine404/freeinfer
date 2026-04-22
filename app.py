"""
FreeInfer - Free AI Token Inference for Everyone
A FastAPI app that proxies requests to multiple AI providers.
"""

import os
import json
import asyncio
from typing import Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import httpx
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()

RATE_LIMIT_CHAT = os.getenv("RATE_LIMIT_CHAT", "20/minute")
RATE_LIMIT_PROVIDERS = os.getenv("RATE_LIMIT_PROVIDERS", "60/minute")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="FreeInfer",
    description="Free AI inference API - multiple providers, zero cost to users",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        "enabled": bool(os.getenv("OPENAI_API_KEY")),
    },
    "anthropic": {
        "name": "Anthropic",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-20250414"],
        "enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
    },
    "ollama": {
        "name": "Ollama (Local)",
        "models": ["llama3", "mistral", "gemma"],
        "enabled": True,  # Assumes Ollama could be running locally
    },
}

# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str = Field(..., description="Role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message content")

class ChatRequest(BaseModel):
    provider: str = Field(..., description="Provider: 'openai', 'anthropic', or 'ollama'")
    model: Optional[str] = Field(None, description="Model name (uses provider default if omitted)")
    messages: list[Message] = Field(..., description="Conversation messages")
    stream: bool = Field(False, description="Whether to stream the response")

class ChatResponse(BaseModel):
    provider: str
    model: str
    content: str
    usage: Optional[dict] = None

# ---------------------------------------------------------------------------
# Provider Implementations
# ---------------------------------------------------------------------------

async def call_openai(messages: list[dict], model: str, stream: bool) -> AsyncGenerator | dict:
    """Call OpenAI-compatible API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }

    if stream:
        async def generate():
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        yield f"data: {json.dumps({'error': body.decode()})}\n\n"
                        return
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            yield f"{line}\n\n"
                        if line.strip() == "data: [DONE]":
                            return
        return generate()
    else:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            data = resp.json()
            return {
                "provider": "openai",
                "model": model,
                "content": data["choices"][0]["message"]["content"],
                "usage": data.get("usage"),
            }


async def call_anthropic(messages: list[dict], model: str, stream: bool) -> AsyncGenerator | dict:
    """Call Anthropic API."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Anthropic API key not configured")

    # Separate system message from conversation
    system_msg = ""
    chat_messages = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        else:
            chat_messages.append(m)

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": chat_messages,
    }
    if system_msg:
        payload["system"] = system_msg

    if stream:
        payload["stream"] = True
        async def generate():
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        yield f"data: {json.dumps({'error': body.decode()})}\n\n"
                        return
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            # Convert Anthropic SSE format to OpenAI-like format
                            try:
                                event_data = json.loads(line[6:])
                                if event_data.get("type") == "content_block_delta":
                                    delta_text = event_data["delta"].get("text", "")
                                    openai_fmt = {
                                        "choices": [{"delta": {"content": delta_text}}]
                                    }
                                    yield f"data: {json.dumps(openai_fmt)}\n\n"
                                elif event_data.get("type") == "message_stop":
                                    yield "data: [DONE]\n\n"
                                    return
                            except json.JSONDecodeError:
                                continue
        return generate()
    else:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            data = resp.json()
            content = "".join(
                block["text"] for block in data["content"] if block["type"] == "text"
            )
            return {
                "provider": "anthropic",
                "model": model,
                "content": content,
                "usage": data.get("usage"),
            }


async def call_ollama(messages: list[dict], model: str, stream: bool) -> AsyncGenerator | dict:
    """Call local Ollama instance."""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }

    if stream:
        async def generate():
            async with httpx.AsyncClient(timeout=120.0) as client:
                try:
                    async with client.stream(
                        "POST",
                        f"{base_url}/api/chat",
                        json=payload,
                    ) as resp:
                        if resp.status_code != 200:
                            body = await resp.aread()
                            yield f"data: {json.dumps({'error': body.decode()})}\n\n"
                            return
                        async for line in resp.aiter_lines():
                            if line.strip():
                                try:
                                    chunk = json.loads(line)
                                    text = chunk.get("message", {}).get("content", "")
                                    if text:
                                        openai_fmt = {
                                            "choices": [{"delta": {"content": text}}]
                                        }
                                        yield f"data: {json.dumps(openai_fmt)}\n\n"
                                    if chunk.get("done"):
                                        yield "data: [DONE]\n\n"
                                        return
                                except json.JSONDecodeError:
                                    continue
                except httpx.ConnectError:
                    yield f"data: {json.dumps({'error': 'Ollama is not running. Start it with: ollama serve'})}\n\n"
        return generate()
    else:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{base_url}/api/chat",
                    json=payload,
                )
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail=resp.text)
                data = resp.json()
                return {
                    "provider": "ollama",
                    "model": model,
                    "content": data["message"]["content"],
                    "usage": None,
                }
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Ollama is not running. Start it with: ollama serve",
            )


PROVIDER_HANDLERS = {
    "openai": {"handler": call_openai, "default_model": "gpt-4o-mini"},
    "anthropic": {"handler": call_anthropic, "default_model": "claude-sonnet-4-20250514"},
    "ollama": {"handler": call_ollama, "default_model": "llama3"},
}

# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check for container orchestration and uptime monitoring."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "providers_enabled": [k for k, v in PROVIDERS.items() if v["enabled"]],
    }


@app.get("/api/providers")
@limiter.limit(RATE_LIMIT_PROVIDERS)
async def list_providers(request: Request):
    """List available providers and their models."""
    return {
        "providers": {
            k: v for k, v in PROVIDERS.items() if v["enabled"]
        }
    }


@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT_CHAT)
async def chat(request: Request, req: ChatRequest):
    """Send a chat completion request (non-streaming)."""
    if req.provider not in PROVIDER_HANDLERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    handler_info = PROVIDER_HANDLERS[req.provider]
    model = req.model or handler_info["default_model"]
    messages = [m.model_dump() for m in req.messages]

    if req.stream:
        generator = await handler_info["handler"](messages, model, stream=True)
        return StreamingResponse(generator, media_type="text/event-stream")

    result = await handler_info["handler"](messages, model, stream=False)
    return JSONResponse(content=result)


@app.post("/api/chat/stream")
@limiter.limit(RATE_LIMIT_CHAT)
async def chat_stream(request: Request, req: ChatRequest):
    """Send a streaming chat completion request."""
    if req.provider not in PROVIDER_HANDLERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    handler_info = PROVIDER_HANDLERS[req.provider]
    model = req.model or handler_info["default_model"]
    messages = [m.model_dump() for m in req.messages]

    generator = await handler_info["handler"](messages, model, stream=True)
    return StreamingResponse(generator, media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Serve Frontend
# ---------------------------------------------------------------------------

# Mount /assets for OG images, favicon, etc.
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/assets", StaticFiles(directory=os.path.join(_STATIC_DIR, "assets")), name="assets")


@app.get("/robots.txt", response_class=HTMLResponse)
async def robots_txt():
    return HTMLResponse(
        content="User-agent: *\nAllow: /\nSitemap: https://freeinfer.dev/sitemap.xml\n",
        media_type="text/plain",
    )


@app.get("/sitemap.xml", response_class=HTMLResponse)
async def sitemap_xml():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://freeinfer.dev/</loc><priority>1.0</priority></url>
  <url><loc>https://freeinfer.dev/chat</loc><priority>0.9</priority></url>
  <url><loc>https://freeinfer.dev/docs-page</loc><priority>0.8</priority></url>
</urlset>"""
    return HTMLResponse(content=xml, media_type="application/xml")


@app.get("/", response_class=HTMLResponse)
async def serve_home():
    """Serve the marketing landing page."""
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html")) as f:
        return HTMLResponse(content=f.read())


@app.get("/chat", response_class=HTMLResponse)
async def serve_chat():
    """Serve the chat UI."""
    with open(os.path.join(os.path.dirname(__file__), "static", "chat.html")) as f:
        return HTMLResponse(content=f.read())


@app.get("/docs-page", response_class=HTMLResponse)
async def serve_docs():
    """Serve the API documentation page."""
    with open(os.path.join(os.path.dirname(__file__), "static", "docs.html")) as f:
        return HTMLResponse(content=f.read())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
