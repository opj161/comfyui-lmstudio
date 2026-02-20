import torch
from src.lmstudio.utils import tensor_to_base64

def test_tensor_to_base64() -> None:
    # Create a mock tensor torch.zeros((1, 512, 512, 3), dtype=torch.float32).
    mock_tensor = torch.zeros((1, 512, 512, 3), dtype=torch.float32)

    result = tensor_to_base64(mock_tensor)

    # Assert that the output is a string and starts with "data:image/jpeg;base64,".
    assert isinstance(result, str)
    assert result.startswith("data:image/jpeg;base64,")
    assert len(result) > 100
