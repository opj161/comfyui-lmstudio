# Architectural Blueprint: ComfyUI LM Studio Node

## 1. System Overview & Data Flow

The system acts as a bidirectional bridge between ComfyUI's synchronous/tensor-based ecosystem and LM Studio's asynchronous/text-based inference engine.

**The Execution Flow:**

1.  **Input Ingestion:** The node receives user inputs (Text Prompt, Configs) and conditionally accepts Image Tensors from upstream ComfyUI nodes.
2.  **Data Transformation:** PyTorch Image Tensors are converted into optimized Base64 JPEG strings in memory.
3.  **Payload Routing:** Based on the user's selected `connection_mode`, the request is routed either through the native `lmstudio-python` SDK or a raw HTTP REST client (`aiohttp`).
4.  **Streaming & UI Updates:** As LM Studio generates tokens, the backend intercepts them and pushes them over ComfyUI's WebSocket to a custom JavaScript extension, updating the node's UI in real-time.
5.  **Finalization:** Once complete, the node aggregates the text, reasoning tokens, and execution statistics, passing them to downstream ComfyUI nodes.

---

## 2. Project Directory Structure

A flat, modular structure ensures code readability without unnecessary abstraction.

```text
ComfyUI-LMStudio-Node/
│
├── __init__.py               # Node registration and entry point
├── node.py                   # Core ComfyUI V3 Node definition
├── client.py                 # Dual-mode execution engine (SDK & REST API)
├── utils.py                  # Tensor-to-Base64 conversion and helpers
└── web/
    └── js/
        └── lmstudio_ui.js    # Frontend extension for real-time streaming
```

---

## 3. Core Components Breakdown

### 3.1. The Orchestration Layer (`node.py`)

This component uses ComfyUI's modern V3 API schema (`comfy_api.latest.io`). It defines the visual representation of the node and acts as the traffic controller.

**Design Decisions:**

- **Unified Interface:** A single node uses an `optional` image input. If no image is connected, it behaves as a standard LLM. If connected, it formats a multimodal payload.
- **Lazy Evaluation:** The image input is marked as `lazy=True`. If the node is bypassed, the heavy upstream image generation (e.g., Stable Diffusion) is skipped, saving compute.

**Schema Specification:**

- **Inputs:**
    - `prompt` (String, multiline=True): The user's query.
    - `image` (Image, optional=True, lazy=True): Upstream PyTorch tensor.
    - `model_id` (String): e.g., `qwen2.5-7b-instruct`.
    - `connection_mode` (Combo): `["SDK", "REST"]`.
    - `server_url` (String): e.g., `http://127.0.0.1:1234` (Used if REST mode is selected).
    - `temperature` (Float): Generation randomness [0.0 - 2.0].
    - `max_tokens` (Int): Generation limit (-1 for infinite).
    - `debug_mode` (Boolean): Enables verbose console logging.
- **Hidden Inputs:**
    - `unique_id` (Hidden): Required to target WebSocket messages to the specific UI node instance.
- **Outputs:**
    - `response_text` (String): The standard LLM reply.
    - `reasoning_text` (String): The extracted "thinking" tokens (e.g., from DeepSeek R1).
    - `statistics` (String): Formatted string containing TPS, TTFT, and Token counts.

### 3.2. Data Transformation Layer (`utils.py`)

LM Studio's vision models require Base64 encoded images, whereas ComfyUI passes images as PyTorch Tensors.

**Processing Steps:**

1.  **Extract:** ComfyUI tensors arrive as batches `[Batch, Height, Width, Channels]`. We slice `tensor[0]` to process the first image.
2.  **Scale:** ComfyUI tensors use `float32` in the range `[0.0, 1.0]`. We multiply by 255 and cast to `uint8`.
3.  **Encode:** Convert the Numpy array to a PIL Image, save it to an in-memory `BytesIO` buffer as a JPEG (to minimize API payload size compared to PNG), and apply Base64 encoding.

### 3.3. Dual-Mode Execution Engine (`client.py`)

To satisfy the "Dual Mode Support" requirement without over-engineering, we use a single asynchronous router function that branches based on the connection mode.

**Mode A: LM Studio SDK (Recommended)**

- **Technology:** `lmstudio-python` via `AsyncClient`.
- **Flow:**
    1. Initialize `lms.AsyncClient()`.
    2. Request a model handle via `await client.llm.model(model_id)`.
    3. Invoke `await model.respond_stream(messages, config)`.
    4. Iterate asynchronously: `async for chunk in stream:`.
    5. Check `chunk.type`. If `"reasoning.delta"`, route to the reasoning UI. If `"message.delta"`, route to the main text UI.
    6. Call `stream.result().stats` to extract built-in real-time statistics (Tokens Per Second, Time To First Token).

**Mode B: REST API (Fallback/Remote Server)**

- **Technology:** `aiohttp.ClientSession`.
- **Flow:**
    1. Format the payload conforming to OpenAI's `/v1/chat/completions` specification.
    2. Open an async POST request with `stream=True`.
    3. Read the stream line-by-line (`async for line in response.content:`).
    4. Parse the Server-Sent Events (SSE) removing the `data: ` prefix.
    5. Inspect the JSON deltas. Look for `delta.content` (normal text) and `delta.reasoning_content` (thinking tokens).
    6. _Note on Stats:_ In REST mode, calculate Time To First Token (TTFT) and Tokens Per Second (TPS) manually using Python's `time.time()`.

### 3.4. Communication & Real-time Visualization (`web/js/lmstudio_ui.js`)

To prevent ComfyUI from freezing during a 30-second text generation, we must decouple the generation process from the UI rendering using WebSockets.

**Backend Dispatch (Python):**
Inside the streaming loop in `client.py`, the backend calls:
`PromptServer.instance.send_sync("lmstudio_node_update", payload)`
The payload contains the `node_id`, `chunk_type` ("text" or "reasoning"), and the `text_chunk`.

**Frontend Reception (JavaScript):**

1.  **Registration:** Use `app.registerExtension` to hook into ComfyUI's startup.
2.  **Widget Injection:** During `beforeRegisterNodeDef`, intercept the creation of the LM Studio node and inject a custom read-only multi-line textarea widget directly onto the node canvas.
3.  **Event Listener:** Hook into `api.addEventListener("lmstudio_node_update", ...)`.
4.  **DOM Manipulation:** When an event fires, find the node by `node_id`.
    - If `chunk_type` is "reasoning", prepend a brain/thought bubble emoji (💭) and append the text in italicized format (or simply append to a dedicated reasoning widget).
    - If `chunk_type` is "text", append normally.
    - Call `app.graph.setDirtyCanvas(true, false)` to force LiteGraph to visually update the node without halting the main thread.

---

## 4. Execution Flow Diagram

This represents a single, complete lifecycle of the node during a ComfyUI prompt execution.

1.  **`execute()` triggered** in `node.py`.
2.  Check for `image`. If present, pass to `utils.py` -> receive `base64_string`.
3.  Build `messages` array.
4.  Clear previous text widgets on the frontend via an initial WebSocket "clear" message.
5.  Call `client.py -> generate_response()`.
6.  `generate_response()` connects to LM Studio (via SDK or REST).
7.  **[Streaming Loop Begins]**
    - Receive token chunk.
    - Identify as standard text or thinking token.
    - Send WebSocket event `lmstudio_node_update` to frontend.
    - Frontend JS updates the node's textarea widget.
8.  **[Streaming Loop Ends]**
    - Extract execution stats (TPS, Input/Output Token counts).
    - Log to console if `debug_mode == True`.
9.  Aggregate full strings.
10. Return `io.NodeOutput(response_text, reasoning_text, stats)`.
11. Downstream ComfyUI nodes receive the generated strings.

---

## 5. Implementation Considerations & Best Practices

To ensure this node is robust within the ComfyUI ecosystem, the following guardrails are integrated into the blueprint:

- **Non-Blocking Network I/O:**
  The execution method _must_ be defined as `async def execute`. Using synchronous `requests.post()` would lock the entire ComfyUI server thread, preventing users from moving nodes or seeing progress bars while the LLM generates.
- **Error Handling Isolation:**
  Network timeouts, LM Studio server crashes, or missing models must be caught gracefully within `client.py`. If an exception occurs, the node should catch it, print the stack trace if `debug_mode` is enabled, and return a clear `io.NodeOutput` string stating `"Error: LM Studio connection failed."` rather than crashing the ComfyUI pipeline.
- **Hardware Symbiosis:**
  Because ComfyUI (Image Generation) and LM Studio (Text Generation) often share the same GPU, the node allows LM Studio to manage its VRAM natively via the REST/SDK defaults. By keeping the node architecture strictly to API communication, it avoids manual PyTorch memory collisions.
