### 1. ComfyUI Backend (Orchestration & Node Definition)

These files contain the specifications for building the modern V3 node, managing inputs (lazy/optional), and handling PyTorch image tensors.

- **.docs/comfyui-docs/custom-nodes/v3_migration.mdx**
    - **Why you need it:** This is the most critical file for the backend. It details the new `comfy_api.latest` V3 schema, how to inherit from `io.ComfyNode`, how to use `define_schema(cls) -> io.Schema`, and how to implement `async def execute`. It also covers how to define `io.Hidden.unique_id` which is required for targeting WebSocket updates to a specific node UI.
- **.docs/comfyui-docs/custom-nodes/backend/lazy_evaluation.mdx**
    - **Why you need it:** Explains how to set `lazy=True` on the optional Image input to prevent upstream image generation nodes (like a heavy SDXL workflow) from executing if the LM Studio node is currently bypassed. Includes the `check_lazy_status` implementation.
- **.docs/comfyui-docs/custom-nodes/backend/more_on_inputs.mdx**
    - **Why you need it:** Provides context on `Hidden and Flexible inputs`, specifically how `UNIQUE_ID` works under the hood to map the Python backend instance to the JavaScript frontend instance.
- **.docs/comfyui-docs/custom-nodes/backend/images_and_masks.mdx**
    - **Why you need it:** Explains that ComfyUI passes images as `torch.Tensor` with shape `[B, H, W, C]`. You will need this to correctly slice and convert the tensor array into a PIL Image and eventually a Base64 string for LM Studio's vision models.
- **.docs/comfyui-docs/custom-nodes/backend/snippets.mdx**
    - **Why you need it:** Contains the exact code snippet for "Load an image", showing the math required to convert `[0.0, 1.0]` float tensors back into standard images using `numpy` and `PIL.Image`.

### 2. ComfyUI Server & Communication (WebSockets)

These files dictate how the Python backend talks to the JavaScript frontend to stream text tokens in real-time.

- **.docs/comfyui-docs/development/comfyui-server/comms_messages.mdx**
    - **Why you need it:** Explains the `PromptServer.instance.send_sync` method. It shows how to dispatch custom message types (e.g., `"lmstudio.stream.update"`) containing the `node_id` and text chunks from the Python server to the frontend.
- **.docs/comfyui-docs/development/comfyui-server/comms_overview.mdx**
    - **Why you need it:** Gives a high-level overview of the `aiohttp` framework and `asyncio` architecture underlying ComfyUI, reinforcing why the `execute` method must be `async` to prevent blocking the server during API calls to LM Studio.

### 3. ComfyUI Frontend (Real-Time UI & Javascript)

These files guide the creation of the custom UI widget that displays the streaming text and reasoning tokens directly on the node canvas.

- **.docs/comfyui-docs/custom-nodes/js/javascript_overview.mdx**
    - **Why you need it:** Covers the basics of how to export a `WEB_DIRECTORY` from your Python `__init__.py` so ComfyUI knows to load your custom `.js` file.
- **.docs/comfyui-docs/custom-nodes/js/javascript_hooks.mdx**
    - **Why you need it:** Details the `beforeRegisterNodeDef` and `setup()` hooks. You will use `setup()` to listen for the WebSocket events (`api.addEventListener`), and `beforeRegisterNodeDef` to inject a custom text display widget onto the node when it is created.
- **.docs/comfyui-docs/custom-nodes/js/javascript_objects_and_hijacking.mdx**
    - **Why you need it:** Documents the `ComfyApp` and `ComfyNode` objects. You'll need to reference `app.graph.getNodeById()` to find the specific node receiving the text stream, and `app.graph.setDirtyCanvas(true, false)` to force the UI to repaint when new text arrives.

### 4. LM Studio Execution Engine (SDK & REST API)

These files define how to structure requests, handle streaming tokens, and pass multimodal (image) data to LM Studio.

- **.docs/lmstudio-docs/1_python/1_getting-started/project-setup.md**
    - **Why you need it:** Details how to import and initialize the `lmstudio` Python SDK, including setting up the `AsyncClient` for asynchronous environments.
- **.docs/lmstudio-docs/1_python/1_llm-prediction/chat-completion.md**
    - **Why you need it:** Contains the core reference for using `await model.respond_stream()`. Crucially, it explains how to use `async for fragment in prediction_stream:` to capture streaming chunks, and how to call `prediction_stream.result().stats` to get the tokens-per-second (TPS) and time-to-first-token (TTFT) metrics.
- **.docs/lmstudio-docs/1_python/1_llm-prediction/image-input.md**
    - **Why you need it:** Shows how the SDK handles Vision models. Note: Because ComfyUI provides PyTorch tensors rather than file paths, you will need to map your Base64 conversion to the appropriate format expected by the LM Studio payload (often standard OpenAI base64 data URIs).
- **.docs/lmstudio-docs/1_developer/2_rest/chat.md**
    - **Why you need it:** The official specification for the `POST /api/v1/chat` endpoint. You will need this to build the fallback REST API execution mode, detailing exactly how the `input` array takes both `{"type": "text"}` and `{"type": "image", "data_url": "..."}` objects.
- **.docs/lmstudio-docs/1_developer/2_rest/streaming-events.md**
    - **Why you need it:** Essential for parsing the REST API stream. It details the exact Server-Sent Event (SSE) structure, such as `message.delta` for standard text and `reasoning.delta` for "thinking" tokens.
