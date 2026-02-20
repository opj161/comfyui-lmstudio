# API_AND_DATA_CONTRACTS.md

**Target Audience:** AI Coding Assistant
**Purpose:** This document strictly defines the data structures, transformations, and network payloads required to bridge ComfyUI and LM Studio. Rely on these exact schemas to prevent hallucinating incorrect tensor shapes or API payloads.

## Contract 1: ComfyUI Image Tensors -> Base64 Strings

ComfyUI passes images into the `execute` method as PyTorch Tensors. LM Studio expects Base64 encoded JPEG/PNG strings.

- **ComfyUI Input Format:** `torch.Tensor` of shape `[Batch, Height, Width, Channels]`.
- **Data Type:** `torch.float32` ranging from `0.0` to `1.0`.
- **Channels:** Usually 3 (RGB).
- **Required Transformation Logic (in `utils.py`):**
    1. Check if the tensor is `None`. If so, skip.
    2. Extract the first image from the batch: `img_tensor = tensor[0]`.
    3. Scale values: `(img_tensor.cpu().numpy() * 255.0).clip(0, 255).astype(np.uint8)`.
    4. Convert to PIL: `Image.fromarray(img_np)`.
    5. Save to `io.BytesIO()` as `"JPEG"`.
    6. Base64 encode and prepend standard URI: `return f"data:image/jpeg;base64,{encoded_string}"`

## Contract 2: LM Studio REST API Request Payload

When `connection_mode == "REST API"`, you must construct a payload that matches the `POST /api/v1/chat` (OpenAI-compatible) endpoint.

**Target URL:** `http://127.0.0.1:1234/api/v1/chat`

**Text-Only Payload:**

```json
{
    "model": "<model_id>",
    "messages": [
        {
            "role": "user",
            "content": "<prompt>"
        }
    ],
    "temperature": 0.7,
    "max_tokens": -1,
    "stream": true
}
```

**Multimodal (Text + Image) Payload:**

```json
{
    "model": "<model_id>",
    "messages": [
        {
            "role": "user",
            "content": [
                { "type": "text", "text": "<prompt>" },
                {
                    "type": "image_url",
                    "image_url": { "url": "data:image/jpeg;base64,..." }
                }
            ]
        }
    ],
    "temperature": 0.7,
    "max_tokens": -1,
    "stream": true
}
```

## Contract 3: LM Studio Server-Sent Events (SSE) Parsing

When streaming is enabled (`"stream": true`), the REST API responds with Server-Sent Events.

**Raw Stream Format:**

```text
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}
\n
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"reasoning_content":"Thinking..."},"finish_reason":null}]}
```

**Parsing Logic Requirements (REST Mode):**

1. Read the async response line by line.
2. If line starts with `data: `, strip the prefix and parse the JSON.
3. If `line.strip() == "data: [DONE]"`, break the loop.
4. Extract text: `chunk_json.get("choices", [{}])[0].get("delta", {}).get("content", "")`
5. Extract reasoning (DeepSeek R1 style): `chunk_json.get("choices", [{}])[0].get("delta", {}).get("reasoning_content", "")`

**Parsing Logic Requirements (SDK Mode):**
If using the `lmstudio-python` SDK (`AsyncClient`):

1. `async for chunk in stream:`
2. Standard text condition: `if chunk.type == "message.delta":` -> use `chunk.content`.
3. Reasoning condition: `if chunk.type == "reasoning.delta":` -> use `chunk.content`.

## Contract 4: Python -> JS WebSocket Protocol

To stream text into the ComfyUI frontend without blocking, the Python backend must dispatch events using `PromptServer`.

**Python Sender Requirement (in `client.py`):**

```python
from server import PromptServer

def send_ws_update(node_id: str, chunk_type: str, content: str):
    # chunk_type must be either "clear", "text", or "reasoning"
    PromptServer.instance.send_sync("lmstudio.stream.update", {
        "node_id": node_id,
        "chunk_type": chunk_type,
        "content": content
    })
```

**JavaScript Receiver Requirement (in `web/js/lmstudio_ui.js`):**

```javascript
import { api } from "../../scripts/api.js";

api.addEventListener("lmstudio.stream.update", (event) => {
    const { node_id, chunk_type, content } = event.detail;
    // 1. Get the node from app.graph.getNodeById(node_id)
    // 2. Locate your custom text widget on that node
    // 3. If chunk_type === "clear", set node.displayWidget.value = ""
    // 4. Otherwise, append the content appropriately
    // 5. Force a UI redraw: app.graph.setDirtyCanvas(true, false);
});
```
