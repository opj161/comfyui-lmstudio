"""Top-level package for comfyui-lmstudio."""

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]

__author__ = """opj161"""
__email__ = "opj161@outlook.com"
__version__ = "0.0.1"

from .src.comfyui-lmstudio.nodes import NODE_CLASS_MAPPINGS
from .src.comfyui-lmstudio.nodes import NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"
