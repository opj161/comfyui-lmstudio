import base64
import io
import torch
import numpy as np
from PIL import Image

def tensor_to_base64(tensor: torch.Tensor, max_size: int = 1024) -> str:
    """
    Convert a ComfyUI PyTorch Tensor image into a Base64-encoded JPEG string.
    Safely resizes the image to prevent OOM errors in the LLM backend.
    """
    if len(tensor.shape) != 4 or tensor.shape[-1] != 3:
        raise ValueError("Expected tensor of shape [B, H, W, 3]")

    image_tensor: torch.Tensor = tensor[0]
    image_np: np.ndarray = np.clip(image_tensor.cpu().numpy() * 255.0, 0, 255).astype(np.uint8)
    pil_image = Image.fromarray(image_np)

    # Safe Resizing Logic to prevent 20MB+ payload strings
    if max(pil_image.width, pil_image.height) > max_size:
        ratio = max_size / max(pil_image.width, pil_image.height)
        new_width = int(pil_image.width * ratio)
        new_height = int(pil_image.height * ratio)
        # Use high-quality downsampling
        pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    pil_image.save(buffer, format="JPEG", quality=85)
    encoded_string: str = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded_string}"
