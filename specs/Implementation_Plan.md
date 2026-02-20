Here is the complete, highly detailed `IMPLEMENTATION_PLAN.md`.

Save this file in your project (e.g., in a `.docs/` or `.github/` folder) and provide it to your AI coding assistant. Instruct the AI to "Execute Phase 1," and only proceed to the next phase when the current one is fully completed and tested.

---

# IMPLEMENTATION_PLAN.md

**Role:** You are an expert Python and JavaScript developer, specializing in ComfyUI Custom Nodes (specifically the V3 `comfy_api.latest` architecture) and the LM Studio API.
**Task:** Execute this implementation plan step-by-step. Do not skip steps. Do not write code for future phases until the current phase is completed, linted, and reviewed.

---

## Phase 1: Scaffold Cleanup & Dependencies

_The current scaffold is a legacy V1 boilerplate with some broken paths. We must clean this up first._

- [ ] **1.1 Update `pyproject.toml`**
    - Add the following to the `dependencies` array:
        - `"aiohttp"` (for REST API communication)
        - `"Pillow"` (for image processing)
        - `"numpy"` (for tensor manipulation)
        - `"lmstudio"` (for the official SDK)
        - `"comfyui-frontend-package"` (for V3 frontend compatibility)
- [ ] **1.2 Fix Root `__init__.py`**
    - The current import is `from .src.comfyui-lmstudio.nodes import ...`. This is incorrect.
    - Update it to reflect V3 architecture: remove `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`.
    - Simply import the V3 entry point: `from .src.lmstudio.nodes import comfy_entrypoint`.
    - Keep `WEB_DIRECTORY = "./web"`.
    - Ensure `__all__ = ["comfy_entrypoint", "WEB_DIRECTORY"]`.
- [ ] **1.3 Clean `src/lmstudio/nodes.py`**
    - Delete the legacy `Example` class and its V1 dictionaries (`NODE_CLASS_MAPPINGS`, etc.).
    - Leave the file completely blank, ready for V3 implementation.
- [ ] **1.4 Clean Tests**
    - Delete or clear out `tests/test_lmstudio.py` so the CI doesn't fail on the missing `Example` class.

---

## Phase 2: Data Utilities (`src/lmstudio/utils.py`)

_LM Studio expects Base64 images; ComfyUI provides PyTorch Tensors. This module bridges that gap._

- [ ] **2.1 Create `src/lmstudio/utils.py`**
- [ ] **2.2 Implement `tensor_to_base64(tensor)`**
    - **Input:** A PyTorch Tensor of shape `[B, H, W, C]` with `float32` values from `0.0` to `1.0`.
    - **Processing:**
        - Extract the first image: `image_tensor = tensor[0]`.
        - Multiply by `255.0`, clip to `0, 255`, and cast to `numpy.uint8`.
        - Convert to `PIL.Image`.
        - Save to an `io.BytesIO` buffer using format `"JPEG"` (quality ~85 to save payload size).
        - Base64 encode the buffer.
    - **Output:** A string formatted as `data:image/jpeg;base64,<encoded_string>`.
- [ ] **2.3 Add strict type hints**
    - Ensure `import torch` and proper type hinting (e.g., `tensor: torch.Tensor -> str`).
- [ ] **2.4 Write Tests (`tests/test_utils.py`)**
    - Create a mock tensor `torch.zeros((1, 512, 512, 3), dtype=torch.float32)`.
    - Assert that the output is a string and starts with `"data:image/jpeg;base64,"`.

---

## Phase 3: Execution Engine (`src/lmstudio/client.py`)

_This module handles dual-mode async communication with LM Studio (SDK and REST)._

- [ ] **3.1 Create `src/lmstudio/client.py`**
- [ ] **3.2 Implement WebSocket Dispatcher**
    - Create an async or synchronous helper function `send_ws_update(node_id: str, chunk_type: str, content: str)`.
    - It must use `from server import PromptServer` and call:
      `PromptServer.instance.send_sync("lmstudio.stream.update", {"node_id": node_id, "chunk_type": chunk_type, "content": content})`
- [ ] **3.3 Implement the `LMStudioSDKClient`**
    - Use `import lmstudio as lms`.
    - Create a method `async def generate(...)` that accepts `model_id`, `messages_array`, `temperature`, `max_tokens`, and `node_id`.
    - Use `async with lms.AsyncClient() as client:`.
    - Load the model: `model = await client.llm.model(model_id)`.
    - Stream the response: `stream = await model.respond_stream(messages, config={...})`.
    - Iterate the stream (`async for chunk in stream:`):
        - Identify reasoning tokens (`chunk.type == "reasoning.delta"`) vs standard text (`chunk.type == "message.delta"`).
        - Send chunks to the frontend via `send_ws_update`.
    - Return the final accumulated text, reasoning text, and stats (TPS/TTFT from `stream.result().stats`).
- [ ] **3.4 Implement the `LMStudioRESTClient` (Fallback)**
    - Use `aiohttp.ClientSession`.
    - Target `POST http://127.0.0.1:1234/api/v1/chat`.
    - Set `"stream": True` in the JSON payload.
    - Asynchronously read lines from the response, parse the `data: {...}` JSON blocks (SSE).
    - Extract `delta.content` and `delta.reasoning_content`.
    - Call `send_ws_update` appropriately.
    - _Note: Implement a fallback calculation for Tokens Per Second if stats aren't provided by the SSE stream._

---

## Phase 4: ComfyUI V3 Node Implementation (`src/lmstudio/nodes.py`)

_Defining the actual node using ComfyUI's modern V3 API._

- [ ] **4.1 Imports and Setup**
    - `from comfy_api.latest import io, ui, ComfyNode, ComfyExtension`
    - Import the client functions from `client.py` and `tensor_to_base64` from `utils.py`.
- [ ] **4.2 Define `LMStudioChatNode`**
    - Inherit from `io.ComfyNode`.
    - Implement `@classmethod def define_schema(cls) -> io.Schema:`
        - `node_id="LMStudio_Unified_Chat"`, `display_name="LM Studio Chat"`.
        - **Inputs:**
            - `prompt`: `io.String.Input(multiline=True)`
            - `image`: `io.Image.Input(optional=True, lazy=True)`
            - `model_id`: `io.String.Input(default="local-model")`
            - `connection_mode`: `io.Combo.Input(options=["SDK", "REST API"])`
            - `temperature`: `io.Float.Input(default=0.7)`
            - `max_tokens`: `io.Int.Input(default=-1)`
        - **Hidden:**
            - `io.Hidden.unique_id` (Crucial for linking the backend stream to the frontend widget).
        - **Outputs:**
            - `text`: `io.String.Output()`
            - `reasoning`: `io.String.Output()`
            - `stats`: `io.String.Output()`
- [ ] **4.3 Implement Lazy Evaluation**
    - Create `@classmethod def check_lazy_status(cls, image, **kwargs) -> list[str]:`
    - If `image` is `None` but the user provided an image connection, do _not_ require it unless a specific toggle is set, or simply return `[]` to accept it as missing. (Follow `lazy_evaluation.mdx` logic).
- [ ] **4.4 Implement `execute` Method**
    - `@classmethod async def execute(cls, prompt: str, connection_mode: str, model_id: str, temperature: float, max_tokens: int, image: torch.Tensor | None = None, **kwargs) -> io.NodeOutput:`
    - **Logic:**
        1. Extract `node_id = cls.hidden.unique_id`.
        2. Build the `messages` payload. If `image` exists, use `tensor_to_base64` and format as a multimodal vision message.
        3. Route to the correct client based on `connection_mode`.
        4. Return `io.NodeOutput(final_text, final_reasoning, stats_string)`.
- [ ] **4.5 Extension Entrypoint**
    - Create class `LMStudioExtension(ComfyExtension)`.
    - `async def get_node_list(self): return [LMStudioChatNode]`
    - `async def comfy_entrypoint() -> ComfyExtension: return LMStudioExtension()`

---

## Phase 5: Real-time UI (Frontend Extension)

_Capturing the WebSocket stream to display text live on the node canvas._

- [ ] **5.1 Create `web/js/lmstudio_ui.js`**
- [ ] **5.2 Register Extension**
    - `import { app } from "../../scripts/app.js";`
    - `import { api } from "../../scripts/api.js";`
    - `app.registerExtension({ name: "LMStudio.UnifiedChat", ... })`
- [ ] **5.3 Inject Custom Widget (`beforeRegisterNodeDef`)**
    - Check if `nodeData.name === "LMStudio_Unified_Chat"`.
    - Override `onNodeCreated`:
        - Add a custom multiline text widget to the node: `this.displayWidget = this.addWidget("text", "Output Stream", "", "output");`
        - Ensure it is read-only.
- [ ] **5.4 Handle WebSocket Event (`setup`)**
    - Listen for `"lmstudio.stream.update"` via `api.addEventListener`.
    - Extract `node_id`, `chunk_type`, and `content`.
    - Locate the node: `const node = app.graph.getNodeById(node_id);`
    - If found, append the text to `node.displayWidget.value`.
    - If `chunk_type === "reasoning"`, optionally prepend a "💭" or format differently.
    - Call `app.graph.setDirtyCanvas(true, false)` to visually update the node immediately.

---

## Phase 6: Code Quality & Testing

_Ensuring the code passes the strict requirements defined in `pyproject.toml`._

- [ ] **6.1 Linting**
    - Run `ruff check . --fix`. Ensure no `eval` or `exec` calls exist.
- [ ] **6.2 Type Checking**
    - Run `mypy .`. Fix any missing type hints (Strict mode is enabled).
- [ ] **6.3 Write Node Execution Test (`tests/test_lmstudio.py`)**
    - Use `unittest.mock.AsyncMock` or `pytest-asyncio`.
    - Mock the `send_ws_update` function.
    - Mock the `BaseLMClient` so no real network requests are made.
    - Test that `LMStudioChatNode.execute()` correctly parses inputs and returns a formatted `io.NodeOutput`.
- [ ] **6.4 Final Build Check**
    - Ensure the GitHub Action `.github/workflows/build-pipeline.yml` will pass.
