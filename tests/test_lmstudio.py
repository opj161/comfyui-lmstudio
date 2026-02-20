import pytest
from unittest.mock import AsyncMock, patch
from comfy_api.latest import io
from src.lmstudio.nodes import LMStudioChatNode

@pytest.mark.asyncio
async def test_lmstudio_node_execute():
    # Mock hidden id
    class MockHidden:
        unique_id = "test_node_id"

    LMStudioChatNode.hidden = MockHidden()

    with patch("src.lmstudio.client.LMStudioSDKClient.generate", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = ("Final Answer", "Thinking...", "TPS: 30")

        result = await LMStudioChatNode.execute(
            prompt="Hello!",
            connection_mode="SDK",
            model_id="qwen-2.5",
            temperature=0.7,
            max_tokens=100,
            server_url="http://localhost:1234",
            debug_mode=False,
            image=None
        )

        assert isinstance(result, io.NodeOutput)
        assert result.text == "Final Answer"
        assert result.reasoning == "Thinking..."
        assert result.stats == "TPS: 30"

        # Verify it called the correct generator
        mock_generate.assert_called_once_with(
            model_id="qwen-2.5",
            prompt="Hello!",
            base64_image=None,
            temperature=0.7,
            max_tokens=100,
            node_id="test_node_id"
        )
