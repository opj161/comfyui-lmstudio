# CODING_STANDARDS_AND_TESTING.md

**Target Audience:** AI Coding Assistant
**Purpose:** Your code will be evaluated by an automated GitHub Actions pipeline. The `pyproject.toml` defines highly strict rules for `ruff` (linting) and `mypy` (type checking). If you violate these rules, the build will fail.

## 1. Strict Typing Rules (`mypy`)

The `pyproject.toml` is configured with `strict = true`, `warn_unreachable = true`, and `warn_no_return = true`.

**Rules:**

- **Every function must have type hints** for both arguments and return values.
- **Use modern union types:** Use `X | None` instead of `Optional[X]`.
- **`kwargs` must be typed:** Use `**kwargs: typing.Any`.
- **No missing returns:** If a function does not return a value, explicitly type it as `-> None`.

**Correct Example:**

```python
import typing
import torch
from comfy_api.latest import io

@classmethod
async def execute(cls, prompt: str, model_id: str, temperature: float,
                  max_tokens: int, debug_mode: bool, image: torch.Tensor | None = None,
                  **kwargs: typing.Any) -> io.NodeOutput:
    pass
```

## 2. Linting & Code Quality (`ruff`)

The `pyproject.toml` enforces strict Ruff linting, explicitly checking for the `S` (flake8-bandit) and `F` (Pyflakes) rules.

**Rules:**

- **NO `eval()` or `exec()`:** Rules `S102` and `S307` will instantly fail the build if you use `exec` or `eval`. Use `json.loads()` for parsing.
- **Line length limit:** Keep lines under 140 characters.
- **Double quotes:** You must use double quotes `" "` for strings, not single quotes `' '` (enforced by `inline-quotes = "double"`).
- **No unused imports:** Clean up your imports. `Ruff` will fail if there is an unused import.

## 3. Asynchronous Programming Constraints

ComfyUI operates an asynchronous web server. Blocking the main thread will cause the entire UI to freeze for the user.

**Rules:**

- **Never use `requests`:** The `requests` module is synchronous.
- **Always use `aiohttp` or `AsyncClient`:** When calling LM Studio's REST API, you must use `aiohttp.ClientSession`. When using the SDK, use `lms.AsyncClient()`.
- **Never use `time.sleep()`:** If you need a delay, use `await asyncio.sleep()`.

## 4. Testing Strategy (`pytest`)

The CI pipeline runs `pytest tests/`. The runner does _not_ have an LM Studio server running, nor does it have a full ComfyUI runtime initialized.

**Rules:**

- **Mock Network Calls:** You must use `unittest.mock.AsyncMock` or `unittest.mock.patch` to mock outgoing calls to LM Studio. Do not attempt actual network requests in tests.
- **Mock ComfyUI Server:** As shown in `WEBSOCKET_PROTOCOL.md`, testing environments will not have `server.PromptServer` initialized. Ensure your code safely falls back if `PromptServer` is missing.
- **Test Async Functions:** Because your `execute` function and client generation functions are `async`, you must mark your pytest functions with `@pytest.mark.asyncio`. (Note: Make sure `pytest-asyncio` is added to your dev dependencies if it isn't already).

**Test Example (`tests/test_client.py`):**

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.lmstudio.client import generate_response

@pytest.mark.asyncio
async def test_generate_response_sdk_mode() -> None:
    # Arrange
    prompt = "Hello"
    model_id = "test-model"

    # We must mock the lmstudio AsyncClient so it doesn't make real requests
    with patch("lmstudio.AsyncClient") as MockClient:
        # Setup the mock chain to return a fake stream/result
        mock_instance = MockClient.return_value.__aenter__.return_value
        mock_model = AsyncMock()
        mock_instance.llm.model = AsyncMock(return_value=mock_model)

        # Act
        # (Assuming generate_response is an async function in your client.py)
        # text, reasoning, stats = await generate_response(...)

        # Assert
        # assert mock_instance.llm.model.called
```

## Summary Checklist for AI:

1. [ ] Did I use double quotes for all strings?
2. [ ] Are all my function signatures fully type-hinted?
3. [ ] Are my LM Studio API calls explicitly asynchronous (`aiohttp` / `AsyncClient`)?
4. [ ] Did I write `@pytest.mark.asyncio` tests that mock the network?
5. [ ] Did I avoid `eval` and `exec` entirely?
