"""Top-level package for comfyui-lmstudio."""

__all__ = [
    "comfy_entrypoint",
    "WEB_DIRECTORY",
]

__version__ = "0.0.1"

try:
    from .src.lmstudio.nodes import comfy_entrypoint
except ImportError:
    from src.lmstudio.nodes import comfy_entrypoint

WEB_DIRECTORY = "./web"
