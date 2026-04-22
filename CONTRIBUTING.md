# Contributing to FreeInfer

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/freeinfer.git
cd freeinfer
```

### 2. Set up Python environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

## Running Locally

Start the dev server:

```bash
uvicorn app:app --reload
```

The API will be available at `http://localhost:8000`.

**Important:** Create a `.env` file in the project root with your API keys:

```
OPENAI_API_KEY=sk_...
ANTHROPIC_API_KEY=sk_...
OLLAMA_BASE_URL=http://localhost:11434
```

Only the keys for providers you want to test are required. Ollama runs locally by default.

## Running Tests

```bash
pytest -v
```

Tests live in the `tests/` directory. Add tests for any new functionality.

## Code Style

Format code with Black:

```bash
black .
```

Lint with Ruff:

```bash
ruff check .
```

Run both before submitting a PR.

## Adding a New Provider

1. Create a new async handler function in `app.py` following the existing patterns:

```python
async def call_newprovider(messages: list[dict], model: str, stream: bool) -> AsyncGenerator | dict:
    """Call NewProvider API."""
    api_key = os.getenv("NEWPROVIDER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="NewProvider API key not configured")
    
    # Build request payload
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    
    if stream:
        async def generate():
            # Yield SSE events: f"data: {json.dumps(event)}\n\n"
            # End with "data: [DONE]\n\n"
            pass
        return generate()
    else:
        # Return dict with keys: provider, model, content, usage
        return {"provider": "newprovider", "model": model, "content": "...", "usage": None}
```

2. Register the handler in `PROVIDER_HANDLERS`:

```python
PROVIDER_HANDLERS = {
    "newprovider": {"handler": call_newprovider, "default_model": "model-name"},
    # ... existing entries
}
```

3. Add the provider to `PROVIDERS` config with enabled status and models list:

```python
PROVIDERS = {
    "newprovider": {
        "name": "NewProvider",
        "models": ["model1", "model2"],
        "enabled": bool(os.getenv("NEWPROVIDER_API_KEY")),
    },
    # ... existing entries
}
```

4. Add tests for your new provider in `tests/`.

## Pull Request Process

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `pytest -v`
5. Format and lint: `black . && ruff check .`
6. Commit and push: `git push origin feature/your-feature`
7. Open a PR with a clear description of what you've done

That's it! We'll review and merge once tests pass.

## Questions?

Open an issue or ask in the PR. We're here to help.
