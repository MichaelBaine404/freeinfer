![FreeInfer](./static/assets/og-image.svg)

# FreeInfer

**Free AI inference for every developer.** Run GPT-4o, Claude, and Ollama models through a single OpenAI-compatible API endpoint — no API keys required from the client, self-hostable, and production-ready.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![Open Source](https://img.shields.io/badge/Open%20Source-Yes-brightgreen)

## What is FreeInfer?

FreeInfer is a lightweight FastAPI proxy that unifies three major AI inference providers — **OpenAI**, **Anthropic**, and **Ollama** — behind a single OpenAI-compatible API. Deploy it once, give your users or clients one endpoint, and route requests to whichever provider you want. Stream responses in real time. No per-request setup. No client-side API key management.

**Key insight:** Anthropic and Ollama use different streaming formats than OpenAI. FreeInfer translates them on the fly, so your client code stays simple.

## Features

- **Stream responses** in real time using Server-Sent Events (SSE)
- **Three providers, one API:** OpenAI, Anthropic, and Ollama (local or remote)
- **Zero client-side keys:** All provider credentials live on your server
- **OpenAI-compatible endpoint:** Use any OpenAI SDK or `fetch` with the same format
- **Self-hostable:** Run on any server (Docker, Fly, Render, your own hardware)
- **Async/await:** Built on FastAPI with non-blocking I/O for high concurrency
- **Production-ready:** CORS enabled, error handling, streaming SSE support

## Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Then edit `.env` and add your API keys:

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434
```

Only providers with configured keys are enabled. Ollama is always available if running locally.

### 3. Run the server

```bash
uvicorn app:app --reload
```

Visit `http://localhost:8000` to see the landing page, or `http://localhost:8000/chat` for the interactive chat UI.

## API Examples

### Python: Streaming Chat

```python
import httpx

async with httpx.AsyncClient() as client:
    async with client.stream(
        "POST",
        "http://localhost:8000/api/chat/stream",
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello!"}],
        },
    ) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                import json
                data = json.loads(line[6:])
                token = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                print(token, end="", flush=True)
```

### JavaScript: Streaming Chat

```javascript
const response = await fetch("http://localhost:8000/api/chat/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    provider: "openai",
    model: "gpt-4o-mini",
    messages: [{ role: "user", content: "Explain streaming APIs" }],
  }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const text = decoder.decode(value);
  const lines = text.split("\n");
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const data = JSON.parse(line.slice(6));
      const token = data?.choices?.[0]?.delta?.content ?? "";
      process.stdout.write(token);
    }
  }
}
```

## Supported Providers

| Provider | Models | Requires | Notes |
|----------|--------|----------|-------|
| **OpenAI** | `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo` | `OPENAI_API_KEY` | Streaming via `/api/chat/stream` |
| **Anthropic** | `claude-sonnet-4-20250514`, `claude-haiku-4-20250414` | `ANTHROPIC_API_KEY` | Translated from Anthropic SSE format to OpenAI format |
| **Ollama** | `llama3`, `mistral`, `gemma` | Local server or `OLLAMA_BASE_URL` | Runs locally; translated from newline-JSON to OpenAI format |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (none) | OpenAI API key. Leave blank to disable OpenAI. |
| `ANTHROPIC_API_KEY` | (none) | Anthropic API key. Leave blank to disable Anthropic. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server base URL (for local or remote instances). |
| `RATE_LIMIT_CHAT` | (optional) | Rate limit for `/api/chat` (e.g., `20/minute`). Requires `slowapi`. |
| `RATE_LIMIT_PROVIDERS` | (optional) | Rate limit for `/api/providers` (e.g., `60/minute`). Requires `slowapi`. |

## Routes

- **`GET /`** — Landing page with project overview
- **`GET /chat`** — Interactive chat UI (no API key required)
- **`GET /docs-page`** — API documentation page
- **`GET /docs`** — Swagger UI (auto-generated by FastAPI)
- **`POST /api/chat`** — Send a message and get a full response (non-streaming)
- **`POST /api/chat/stream`** — Send a message and stream the response via SSE
- **`GET /api/providers`** — List enabled providers and their models
- **`GET /health`** — Health check (useful for monitoring)
- **`GET /robots.txt`** — Search engine crawl rules
- **`GET /sitemap.xml`** — Sitemap for SEO

## Deploy

### Docker

Build and run in a container:

```bash
docker build -t freeinfer .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  freeinfer
```

### Docker Compose (with Ollama)

For local development or self-hosted deployments with Ollama:

```bash
docker compose up
```

This starts both FreeInfer and Ollama in containers on the same network.

### Fly.io

```bash
fly launch --name freeinfer
fly secrets set OPENAI_API_KEY=sk-...
fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly deploy
```

### Render

1. Push your code to GitHub
2. Create a new Web Service on Render
3. Set the build command: `pip install -r requirements.txt`
4. Set the start command: `uvicorn app:app --host 0.0.0.0 --port 8000`
5. Add secrets for `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`

### Self-hosted

Run on any machine with Python 3.10+:

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
uvicorn app:app --host 0.0.0.0 --port 8000
```

For production, use a process manager like systemd or supervisor, and a reverse proxy like Nginx.

## Architecture

```
┌─────────────┐
│   Client    │
│  (Browser   │
│ or SDK)     │
└──────┬──────┘
       │ POST /api/chat/stream
       │ { provider, model, messages }
       │
       ▼
┌──────────────────┐
│  FreeInfer       │
│  (FastAPI)       │
│                  │
│  ┌────────────┐  │
│  │ Router     │  │
│  └──────┬─────┘  │
│         │        │
│  ┌──────┴─────┐  │
│  │             │  │
│  ▼ OpenAI     ▼  ▼
│ ┌──────┐   ┌──────┐  ┌──────┐
│ │      │   │      │  │      │
│ │ OAI  │   │ Anth │  │Ollama│
│ │      │   │      │  │      │
│ └──┬───┘   └───┬──┘  └──┬───┘
│    │           │        │
│    │ (Translate SSE format to OpenAI standard)
│    │           │        │
│    └───────┬───┴────┬───┘
│            │        │
│            ▼        ▼
│         ┌──────────────┐
│         │ Streaming    │
│         │ Generator    │
│         └──────┬───────┘
└────────────────┼──────────────┘
                 │
                 ▼
         ┌───────────────┐
         │  Server-Sent  │
         │  Events (SSE) │
         └───────────────┘
                 │
                 ▼
            ┌──────────┐
            │  Client  │
            │ Receives │
            │  Tokens  │
            └──────────┘
```

**Key design principle:** Each provider (OpenAI, Anthropic, Ollama) has its own API format. FreeInfer abstracts this away by:
1. Accepting a standard OpenAI-like request
2. Translating it to each provider's format
3. Streaming the response back in OpenAI SSE format

This means your client code never needs to know which provider is running on the backend.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines on:
- Reporting bugs
- Suggesting features
- Submitting pull requests
- Setting up the development environment

## License

[MIT License](./LICENSE) — Use FreeInfer for anything, commercial or personal, as long as you include the license.

## Support

- **Questions?** Open an issue on GitHub
- **Found a bug?** File an issue with reproduction steps
- **Have an idea?** Start a discussion or submit a PR

---

Built with FastAPI, httpx, and async/await. Inspired by the need for a simple, free, and unified AI inference layer.
