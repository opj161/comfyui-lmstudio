Here are the complete, highly detailed `WEBSOCKET_PROTOCOL.md` and `CODING_STANDARDS_AND_TESTING.md` documents.

Save these in your `.docs/assistant_guides/` folder alongside the others. They are designed to give the AI assistant explicit boundaries for real-time frontend/backend communication and strict adherence to your repository's CI/CD pipeline.

---

# WEBSOCKET_PROTOCOL.md

**Target Audience:** AI Coding Assistant
**Purpose:** This document strictly defines the real-time communication pipeline between the ComfyUI Python Backend and the ComfyUI JavaScript Frontend. Because LLM generation is slow, we must stream tokens to the UI via WebSockets to prevent the user experience from freezing.

## 1. Event Definitions

We define two custom WebSocket events for this node:

1.  `"lmstudio.stream.clear"`: Sent at the very beginning of an `execute` call to clear the frontend widget of previous text.
2.  `"lmstudio.stream.update"`: Sent continuously as chunks arrive from the LM Studio API.

### Payload Schema

```json
// For "lmstudio.stream.update"
{
  "node_id": "15",              // Must match the node's UNIQUE_ID
  "chunk_type": "text",         // Either "text" or "reasoning"
  "content": "Hello world"      // The text fragment
}

// For "lmstudio.stream.clear"
{
  "node_id": "15"
}
```

## 2. Python Backend Implementation (Sender)

In `src/lmstudio/client.py` (or `utils.py`), implement a helper class or function to safely dispatch these messages.

**Constraints:**

- You must import `PromptServer` from ComfyUI's core.
- In testing environments, `PromptServer` might not exist. You must handle `ImportError` gracefully so `pytest` doesn't crash.

**Implementation Standard:**

```python
import typing

# Graceful fallback for Pytest environments
try:
    from server import PromptServer
    _server_available = True
except ImportError:
    _server_available = False

def send_ws_clear(node_id: str) -> None:
    if _server_available and PromptServer.instance is not None:
        PromptServer.instance.send_sync("lmstudio.stream.clear", {"node_id": node_id})

def send_ws_update(node_id: str, chunk_type: str, content: str) -> None:
    if _server_available and PromptServer.instance is not None:
        PromptServer.instance.send_sync("lmstudio.stream.update", {
            "node_id": node_id,
            "chunk_type": chunk_type,
            "content": content
        })
```

## 3. JavaScript Frontend Implementation (Receiver)

In `web/js/lmstudio_ui.js`, you must register a ComfyUI extension that injects a text display widget into the node and listens for the WebSocket events.

**Constraints:**

- **Do not use generic `alert()` or `console.log()`** as the primary output. You must update the node visually.
- **Prevent Canvas Freezing:** Use `app.graph.setDirtyCanvas(true, false)` to visually update the node without halting the main thread.

**Implementation Standard:**

```javascript
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "LMStudio.UnifiedChat",

    // 1. Inject the custom widget when the node is created
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "LMStudio_Unified_Chat") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) {
                    onNodeCreated.apply(this, arguments);
                }

                // Add a read-only multiline text widget for streaming display
                this.displayWidget = this.addWidget(
                    "customtext",
                    "Stream",
                    "",
                    "output",
                );
                // Optional: set widget properties so it doesn't try to serialize back to Python
                this.displayWidget.serialize = false;
            };
        }
    },

    // 2. Setup the WebSocket listeners
    async setup() {
        // Handle Clear Event
        api.addEventListener("lmstudio.stream.clear", (event) => {
            const { node_id } = event.detail;
            const node = app.graph.getNodeById(node_id);
            if (node && node.displayWidget) {
                node.displayWidget.value = "";
                app.graph.setDirtyCanvas(true, false);
            }
        });

        // Handle Stream Update Event
        api.addEventListener("lmstudio.stream.update", (event) => {
            const { node_id, chunk_type, content } = event.detail;
            const node = app.graph.getNodeById(node_id);
            if (node && node.displayWidget) {
                // Prepend a thought bubble for reasoning tokens
                const prefix = chunk_type === "reasoning" ? "💭 " : "";

                // Append text to the widget
                if (node.displayWidget.value === undefined)
                    node.displayWidget.value = "";
                node.displayWidget.value += prefix + content;

                // Redraw the canvas to show the new text
                app.graph.setDirtyCanvas(true, false);
            }
        });
    },
});
```
