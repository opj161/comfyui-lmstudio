# SCAFFOLD_REFACTORING_GUIDE.md

**Target Audience:** AI Coding Assistant
**Purpose:** The current codebase contains a legacy ComfyUI V1 boilerplate. You must strictly follow this guide to refactor the codebase into the modern ComfyUI V3 architecture (`comfy_api.latest`). Do not use V1 patterns.

## 🛑 What NOT To Do (Legacy Patterns to Delete)

When you open `src/lmstudio/nodes.py`, you will see legacy patterns. **Delete them entirely.**

- ❌ Do NOT use `@classmethod def INPUT_TYPES(s):`.
- ❌ Do NOT use `RETURN_TYPES = ("IMAGE",)`.
- ❌ Do NOT use `RETURN_NAMES = (...)`.
- ❌ Do NOT use `FUNCTION = "test"`.
- ❌ Do NOT use `NODE_CLASS_MAPPINGS` or `NODE_DISPLAY_NAME_MAPPINGS` dictionaries.

## ✅ What TO Do (V3 Architecture Patterns)

### 1. Fix Root `__init__.py`

The current `__init__.py` has broken import paths referencing `src.comfyui-lmstudio.nodes` which does not match the actual folder structure (`src/lmstudio/nodes.py`). Furthermore, it relies on V1 mappings.
**Rewrite `__init__.py` to exactly this:**

```python
"""Top-level package for comfyui-lmstudio."""

__all__ = [
    "comfy_entrypoint",
    "WEB_DIRECTORY",
]

__version__ = "0.0.1"

from .src.lmstudio.nodes import comfy_entrypoint

WEB_DIRECTORY = "./web"
```

### 2. Base Class Inheritance

All nodes must inherit from `io.ComfyNode` using the latest API.

```python
from comfy_api.latest import io, ComfyExtension, ComfyNode, ui

class LMStudioChatNode(io.ComfyNode):
    # Implementation goes here
```

### 3. Define the Schema (`define_schema`)

Instead of `INPUT_TYPES`, you must implement `@classmethod def define_schema(cls) -> io.Schema:`.
For the `LMStudioChatNode`, it must look like this:

```python
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LMStudio_Unified_Chat",
            display_name="LM Studio Chat",
            category="LM Studio",
            inputs=[
                io.String.Input("prompt", multiline=True),
                io.Image.Input("image", optional=True, lazy=True),
                io.String.Input("model_id", default="local-model"),
                io.Combo.Input("connection_mode", options=["SDK", "REST API"]),
                io.Float.Input("temperature", default=0.7, min=0.0, max=2.0),
                io.Int.Input("max_tokens", default=-1, min=-1),
                io.Boolean.Input("debug_mode", default=False)
            ],
            outputs=[
                io.String.Output(display_name="text"),
                io.String.Output(display_name="reasoning"),
                io.String.Output(display_name="stats")
            ],
            hidden=[
                io.Hidden.unique_id  # Needed for WebSocket targeting
            ]
        )
```

### 4. The Execution Method (`execute`)

The entry point must be an asynchronous class method named exactly `execute` that returns an `io.NodeOutput`.

```python
    @classmethod
    async def execute(cls, prompt: str, model_id: str, connection_mode: str,
                      temperature: float, max_tokens: int, debug_mode: bool,
                      image=None, **kwargs) -> io.NodeOutput:

        node_id = cls.hidden.unique_id

        # ... logic ...

        return io.NodeOutput(final_text, final_reasoning, stats_json)
```

### 5. Extension Entrypoint (`comfy_entrypoint`)

At the bottom of `src/lmstudio/nodes.py`, you must define the `ComfyExtension` that replaces `NODE_CLASS_MAPPINGS`.

```python
class LMStudioExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [LMStudioChatNode]

async def comfy_entrypoint() -> LMStudioExtension:
    return LMStudioExtension()
```
