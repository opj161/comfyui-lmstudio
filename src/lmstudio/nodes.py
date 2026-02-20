import torch
import asyncio
from comfy_api.latest import io, ComfyExtension

from src.lmstudio.client import LMStudioSDKClient, LMStudioRESTClient
from src.lmstudio.utils import tensor_to_base64

class LMStudioChatNode(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LMStudio_Unified_Chat",
            display_name="LM Studio Chat",
            category="LM Studio",
            inputs=[
                io.String.Input("prompt", multiline=True),
                io.Image.Input("image", optional=True),
                io.String.Input("model_id", default="local-model"),
                io.Combo.Input("connection_mode", options=["SDK", "REST API"]),
                io.Float.Input("temperature", default=0.7, min=0.0, max=2.0),
                io.Int.Input("max_tokens", default=-1, min=-1),
                io.String.Input("server_url", default="http://127.0.0.1:1234"),
                io.Boolean.Input("debug_mode", default=False)
            ],
            outputs=[
                io.String.Output(display_name="text"),
                io.String.Output(display_name="reasoning"),
                io.String.Output(display_name="stats")
            ],
            hidden=[
                io.Hidden.unique_id
            ]
        )

    @classmethod
    async def execute(
        cls, 
        prompt: str, 
        connection_mode: str, 
        model_id: str, 
        temperature: float, 
        max_tokens: int,
        server_url: str,
        debug_mode: bool,
        image: torch.Tensor | None = None,
        **kwargs
    ) -> io.NodeOutput:

        node_id = cls.hidden.unique_id
        if image is not None:
            base64_image = await asyncio.to_thread(tensor_to_base64, image)
        else:
            base64_image = None

        if debug_mode:
            print(f"[LM Studio Node] Executing with mode={connection_mode}, model={model_id}")

        if connection_mode == "SDK":
            final_text, final_reasoning, stats_str = await LMStudioSDKClient.generate(
                model_id=model_id,
                prompt=prompt,
                base64_image=base64_image,
                temperature=temperature,
                max_tokens=max_tokens,
                node_id=node_id
            )
        else:
            # REST API mode
            final_text, final_reasoning, stats_str = await LMStudioRESTClient.generate(
                server_url=server_url,
                model_id=model_id,
                prompt=prompt,
                base64_image=base64_image,
                temperature=temperature,
                max_tokens=max_tokens,
                node_id=node_id
            )

        return io.NodeOutput(final_text, final_reasoning, stats_str, ui={"text": [final_text]})

class LMStudioExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [LMStudioChatNode]

async def comfy_entrypoint() -> LMStudioExtension:
    return LMStudioExtension()
