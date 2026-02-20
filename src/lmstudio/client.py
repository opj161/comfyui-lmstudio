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
            config["max_tokens"] = max_tokens

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
                stats_str = f"TPS: {stats.tokens_per_second:.2f}, TTFT: {stats.time_to_first_token:.2f}s"

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

        input_data = []
        input_data.append({
            "type": "text",
            "content": prompt
        })

        if base64_image:
            input_data.append({
                "type": "image",
                "data_url": base64_image
            })

        payload = {
            "model": model_id,
            "input": input_data,
            "stream": True,
            "temperature": temperature
        }

        if max_tokens > 0:
            payload["max_tokens"] = max_tokens

        start_time = time.time()
        first_token_time = 0.0
        token_count = 0

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{server_url}/api/v1/chat", json=payload) as response:
                    # Async read line by line for SSE
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith("data: "):
                            data_str = line_str[6:].strip()
                            if not data_str or data_str == "[DONE]":
                                continue

                            try:
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                
                                # Check for reasoning tokens first
                                if "reasoning_content" in delta and delta["reasoning_content"]:
                                    if token_count == 0:
                                        first_token_time = time.time() - start_time
                                    token_count += 1
                                    
                                    content = delta["reasoning_content"]
                                    final_reasoning += content
                                    send_ws_update(node_id, "reasoning", content)
                                    
                                # Check for standard content
                                elif "content" in delta and delta["content"]:
                                    if token_count == 0:
                                        first_token_time = time.time() - start_time
                                    token_count += 1
                                    
                                    content = delta["content"]
                                    final_text += content
                                    send_ws_update(node_id, "text", content)
                            except json.JSONDecodeError:
                                pass

            # Manual stats calculation
            end_time = time.time()
            total_time = end_time - (start_time + first_token_time)
            tps = token_count / total_time if total_time > 0 else 0

            stats_str = f"TPS: {tps:.2f}, TTFT: {first_token_time:.2f}s, Tokens: {token_count}"
            return final_text, final_reasoning, stats_str

        except Exception as e:
            return f"Error: LM Studio connection failed via REST API. {str(e)}", "", "{}"
