import base64
import json
import aiohttp
from aiohttp import web
import lmstudio as lms

# Import ComfyUI's interrupt manager to handle user cancellations
try:
    import comfy.model_management as model_management
except ImportError:
    model_management = None

_server_available = False
try:
    from server import PromptServer  # type: ignore
    _server_available = True
    
    if _server_available and PromptServer.instance is not None:
        @PromptServer.instance.routes.get("/lmstudio/models")
        async def fetch_lmstudio_models(request):
            """Custom route to fetch models. Accepts a URL parameter for remote REST servers."""
            # Default to localhost if no URL is provided
            base_url = request.query.get("url", "http://127.0.0.1:1234").rstrip("/")
            target_url = f"{base_url}/api/v1/models"
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(target_url, timeout=2) as resp:
                        data = await resp.json()
                        models = [m.get("id") or m.get("key") for m in data.get("data", []) or data.get("models", []) if m.get("type", "llm") == "llm" or m.get("object") == "model"]
                        if not models:
                            models = ["No LLMs found in LM Studio"]
                        return web.json_response({"models": models})
            except Exception:
                return web.json_response({"models": ["LM Studio offline"]})
except ImportError:
    pass

def send_ws_update(node_id: str, chunk_type: str, content: str) -> None:
    if not _server_available or PromptServer.instance is None:
        return
    try:
        PromptServer.instance.send_sync(
            "lmstudio.stream.update", 
            {"node_id": node_id, "chunk_type": chunk_type, "content": content}
        )
    except Exception as e:
        print(f"Failed to send WS update: {e}")

class LMStudioSDKClient:
    @staticmethod
    async def generate(node_id: str, system_prompt: str, prompt: str, base64_image: str | None, json_schema: str, model_id: str, seed: int, temperature: float, max_tokens: int) -> tuple[str, str, str]:
        send_ws_update(node_id, "clear", "")
        final_text = ""
        final_reasoning = ""

        config = {"temperature": temperature, "seed": seed}
        if max_tokens > 0:
            config["maxTokens"] = max_tokens

        # Parse schema safely
        parsed_schema = None
        if json_schema.strip():
            try:
                parsed_schema = json.loads(json_schema)
            except json.JSONDecodeError:
                print("[LM Studio] Warning: Invalid JSON schema provided.")

        try:
            async with lms.AsyncClient() as client:
                model = await client.llm.model(model_id)
                chat = lms.Chat(system_prompt.strip()) if system_prompt.strip() else lms.Chat()
                
                if base64_image:
                    encoded_str = base64_image.split(",")[1] if "," in base64_image else base64_image
                    image_bytes = base64.b64decode(encoded_str)
                    image_handle = await client.files.prepare_image(image_bytes)
                    chat.add_user_message(prompt, images=[image_handle])
                else:
                    chat.add_user_message(prompt)

                if parsed_schema:
                    stream = await model.respond_stream(chat, config=config, response_format=parsed_schema)
                else:
                    stream = await model.respond_stream(chat, config=config)

                async for chunk in stream:
                    # HANDLE INTERRUPTS (User clicked Cancel in ComfyUI)
                    if model_management and model_management.processing_interrupted():
                        print("[LM Studio] Generation cancelled by user.")
                        await stream.cancel()  # <- CRITICAL FIX: Actively cancel the SDK stream
                        break

                    content = getattr(chunk, "content", "")
                    if not content:
                        continue

                    is_reasoning = getattr(chunk, "is_reasoning", False)
                    chunk_type = getattr(chunk, "type", "")
                    
                    if is_reasoning or chunk_type == "reasoning.delta":
                        final_reasoning += content
                        send_ws_update(node_id, "reasoning", content)
                    else:
                        final_text += content
                        send_ws_update(node_id, "text", content)

                # Fetch stats safely (if interrupted, result() might throw an error)
                try:
                    result_obj = stream.result() # Synchronous call
                    stats = result_obj.stats
                    ttft = getattr(stats, "time_to_first_token_sec", 0.0)
                    tokens = getattr(stats, "predicted_tokens_count", 0)
                    stats_str = f"TTFT: {ttft:.2f}s, Tokens: {tokens}"
                except Exception:
                    stats_str = f"Stats unavailable (Interrupted). Tokens generated: {len(final_text)//4}"

                return final_text, final_reasoning, stats_str
        except Exception as e:
            return f"Error: LM Studio connection failed. {str(e)}", "", "{}"

class LMStudioRESTClient:
    @staticmethod
    async def generate(node_id: str, system_prompt: str, server_url: str, model_id: str, prompt: str, base64_image: str | None, json_schema: str, seed: int, temperature: float, max_tokens: int) -> tuple[str, str, str]:
        send_ws_update(node_id, "clear", "")
        final_text = ""
        final_reasoning = ""
        stats_str = "Stats unavailable"

        input_data = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": base64_image}}] if base64_image else prompt

        # Native LM Studio API formatting
        payload = {
            "model": model_id,
            "input": input_data,
            "stream": True,
            "temperature": temperature,
            "seed": seed
        }

        if system_prompt.strip():
            payload["system_prompt"] = system_prompt.strip()

        if max_tokens > 0:
            payload["max_output_tokens"] = max_tokens

        # JSON Schema injection for REST
        if json_schema.strip():
            try:
                schema_dict = json.loads(json_schema)
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "comfyui_structured_output",
                        "strict": True,
                        "schema": schema_dict
                    }
                }
            except json.JSONDecodeError:
                print("[LM Studio] Warning: Invalid JSON schema provided.")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{server_url}/api/v1/chat", json=payload) as response:
                    async for line in response.content:
                        # HANDLE INTERRUPTS (User clicked Cancel in ComfyUI)
                        if model_management and model_management.processing_interrupted():
                            print("[LM Studio] Generation cancelled by user.")
                            break

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
