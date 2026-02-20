import base64
import io
import torch
import numpy as np
from PIL import Image

def tensor_to_base64(tensor: torch.Tensor) -> str:
    """
    Convert a ComfyUI PyTorch Tensor image into a Base64-encoded JPEG string.

    Args:
        tensor: A PyTorch Tensor of shape [B, H, W, C] with float32 values from 0.0 to 1.0.
        
    Returns:
        A Base64 string formatted as a standard data URI.
    """
    if len(tensor.shape) != 4 or tensor.shape[-1] != 3:
        raise ValueError("Expected tensor of shape [B, H, W, 3]")

    # Extract the first image: image_tensor = tensor[0]
    image_tensor: torch.Tensor = tensor[0]

    # Multiply by 255.0, clip to 0, 255, and cast to numpy.uint8
    image_np: np.ndarray = np.clip(image_tensor.cpu().numpy() * 255.0, 0, 255).astype(np.uint8)

    # Convert to PIL.Image
    pil_image = Image.fromarray(image_np)

    # Save to an io.BytesIO buffer using format "JPEG" (quality ~85)
    buffer = io.BytesIO()
    pil_image.save(buffer, format="JPEG", quality=85)

    # Base64 encode the buffer
    encoded_string: str = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded_string}"
