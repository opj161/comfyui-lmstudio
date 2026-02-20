"""Top-level package for comfyui-lmstudio."""

__all__ = [
    "comfy_entrypoint",
    "WEB_DIRECTORY",
]

__version__ = "0.0.1"

try:
    from .src.lmstudio.nodes import comfy_entrypoint
except ImportError as e:
    if "src" not in str(e) and "attempted relative import" not in str(e):
        raise
    from src.lmstudio.nodes import comfy_entrypoint

WEB_DIRECTORY = "./web"
