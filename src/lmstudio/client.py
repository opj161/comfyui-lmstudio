import base64
import json
import time
import aiohttp
import lmstudio as lms

_server_available = False
try:
    from server import PromptServer  # type: ignore
    _server_available = True
except ImportError:
    pass

def send_ws_update(node_id: str, chunk_type: str, content: str) -> None:
    """Helper function to send websocket updates to the ComfyUI frontend."""
    if not _server_available or PromptServer.instance is None:
        return
    # Try sending via PromptServer instance
    try:
        PromptServer.instance.send_sync(
            "lmstudio.stream.update", 
            {
                "node_id": node_id, 
                "chunk_type": chunk_type, 
                "content": content
            }
        )
    except Exception as e:
        print(f"Failed to send WS update: {e}")

class LMStudioSDKClient:
    """Client for connecting via the official LM Studio SDK."""

    @staticmethod
    async def generate(model_id: str, prompt: str, base64_image: str | None, temperature: float, max_tokens: int, node_id: str) -> tuple[str, str, str]:
        send_ws_update(node_id, "clear", "")
        final_text = ""
        final_reasoning = ""

        config = {
            "temperature": temperature,
        }
        if max_tokens > 0:
            config["maxTokens"] = max_tokens

        try:
            async with lms.AsyncClient() as client:
                model = await client.llm.model(model_id)
                chat = lms.Chat()
                
                if base64_image:
                    # Strip the data URI prefix if present and decode base64
                    encoded_str = base64_image.split(",")[1] if "," in base64_image else base64_image
                    image_bytes = base64.b64decode(encoded_str)
                    image_handle = await client.files.prepare_image(image_bytes)
                    chat.add_user_message(prompt, images=[image_handle])
                else:
                    chat.add_user_message(prompt)

                stream = await model.respond_stream(chat, config=config)

                async for chunk in stream:
                    if chunk.type == "reasoning.delta":
                        final_reasoning += chunk.content
                        send_ws_update(node_id, "reasoning", chunk.content)
                    elif chunk.type == "message.delta":
                        final_text += chunk.content
                        send_ws_update(node_id, "text", chunk.content)

                stats = stream.result().stats
                ttft = getattr(stats, "time_to_first_token_sec", 0.0)
                tokens = getattr(stats, "predicted_tokens_count", 0)
                stats_str = f"TTFT: {ttft:.2f}s, Tokens: {tokens}"

                return final_text, final_reasoning, stats_str
        except Exception as e:
            return f"Error: LM Studio connection failed. {str(e)}", "", "{}"

class LMStudioRESTClient:
    """Fallback client for connecting via raw REST API."""

    @staticmethod
    async def generate(server_url: str, model_id: str, prompt: str, base64_image: str | None, temperature: float, max_tokens: int, node_id: str) -> tuple[str, str, str]:
        send_ws_update(node_id, "clear", "")
        final_text = ""
        final_reasoning = ""
        stats_str = "Stats unavailable"

        if base64_image:
            input_data = [
                {"type": "text", "content": prompt},
                {"type": "image", "data_url": base64_image}
            ]
        else:
            input_data = prompt

        payload = {
            "model": model_id,
            "input": input_data,
            "stream": True,
            "temperature": temperature
        }

        if max_tokens > 0:
            payload["max_output_tokens"] = max_tokens

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{server_url}/api/v1/chat", json=payload) as response:
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith("data: "):
                            data_str = line_str[6:].strip()
                            if not data_str or data_str == "[DONE]":
                                continue

                            try:
                                data = json.loads(data_str)
                                evt_type = data.get("type")

                                if evt_type == "reasoning.delta":
                                    content = data.get("content", "")
                                    final_reasoning += content
                                    send_ws_update(node_id, "reasoning", content)
                                    
                                elif evt_type == "message.delta":
                                    content = data.get("content", "")
                                    final_text += content
                                    send_ws_update(node_id, "text", content)
                                
                                elif evt_type == "chat.end":
                                    stats = data.get("result", {}).get("stats", {})
                                    tps = stats.get("tokens_per_second", 0)
                                    ttft = stats.get("time_to_first_token_seconds", 0)
                                    tokens = stats.get("total_output_tokens", 0)
                                    stats_str = f"TPS: {tps:.2f}, TTFT: {ttft:.2f}s, Tokens: {tokens}"
                                    
                                elif evt_type == "error":
                                    err_msg = data.get("error", {}).get("message", "Unknown error")
                                    final_text += f"\n[Error: {err_msg}]"
                                    send_ws_update(node_id, "text", f"\n[Error: {err_msg}]")

                            except json.JSONDecodeError:
                                pass

            return final_text, final_reasoning, stats_str

        except Exception as e:
            return f"Error: LM Studio connection failed via REST API. {str(e)}", "", "{}"
