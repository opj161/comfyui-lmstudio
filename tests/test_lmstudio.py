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
            system_prompt="You are a helpful AI assistant.",
            prompt="Hello!",
            connection_mode={"connection_mode": "SDK"},
            model_id="qwen-2.5",
            json_schema="",
            seed=42,
            temperature=0.7,
            max_tokens=100,
            reasoning_effort="auto",
            stream_output="Waiting...",
            debug_mode=False,
            image=None,
            unique_id="test_node_id"
        )

        assert isinstance(result, io.NodeOutput)
        assert result.text == "Final Answer"
        assert result.reasoning == "Thinking..."
        assert result.stats == "TPS: 30"

        # Verify it called the correct generator
        mock_generate.assert_called_once_with(
            node_id="test_node_id",
            system_prompt="You are a helpful AI assistant.",
            prompt="Hello!",
            base64_image=None,
            json_schema="",
            model_id="qwen-2.5",
            seed=42,
            temperature=0.7,
            max_tokens=100,
            reasoning_effort="auto"
        )


@pytest.mark.asyncio
async def test_lmstudio_node_reasoning_effort_high():
    """Verify that a non-auto reasoning_effort value is correctly passed through."""
    class MockHidden:
        unique_id = "test_node_reasoning"

    LMStudioChatNode.hidden = MockHidden()

    with patch("src.lmstudio.client.LMStudioRESTClient.generate", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = ("Answer", "Deep thinking...", "TPS: 25")

        result = await LMStudioChatNode.execute(
            system_prompt="Think step by step.",
            prompt="Solve this puzzle.",
            connection_mode={"connection_mode": "REST API", "server_url": "http://localhost:1234"},
            model_id="qwen3-8b",
            json_schema="",
            seed=0,
            temperature=0.5,
            max_tokens=500,
            reasoning_effort="high",
            stream_output="Waiting...",
            debug_mode=False,
            image=None,
            unique_id="test_node_reasoning"
        )

        assert isinstance(result, io.NodeOutput)
        assert result.text == "Answer"
        assert result.reasoning == "Deep thinking..."

        mock_generate.assert_called_once_with(
            system_prompt="Think step by step.",
            server_url="http://localhost:1234",
            model_id="qwen3-8b",
            prompt="Solve this puzzle.",
            base64_image=None,
            json_schema="",
            seed=0,
            temperature=0.5,
            max_tokens=500,
            reasoning_effort="high",
            node_id="test_node_reasoning"
        )
