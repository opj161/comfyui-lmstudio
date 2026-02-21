import torch
import asyncio
from comfy_api.latest import io, ComfyExtension

from .client import LMStudioSDKClient, LMStudioRESTClient
from .utils import tensor_to_base64

class LMStudioChatNode(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LMStudio_Unified_Chat",
            display_name="LM Studio Chat",
            category="LM Studio",
            inputs=[
                io.String.Input("system_prompt", multiline=True, default="You are a helpful AI assistant. Describe the image accurately."),
                io.String.Input("prompt", multiline=True),
                io.Image.Input("image", optional=True),
                io.Combo.Input("model_id", options=["Loading models from LM Studio..."]),
                io.DynamicCombo.Input("connection_mode", options=[
                    io.DynamicCombo.Option("SDK", []),
                    io.DynamicCombo.Option("REST API", [
                        io.String.Input("server_url", default="http://localhost:1234")
                    ])
                ]),
                io.String.Input("json_schema", multiline=True, default="", tooltip="Optional: Enforce JSON output using a JSON Schema definition."),
                io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff, control_after_generate=io.ControlAfterGenerate.randomize),
                io.Float.Input("temperature", default=0.7, min=0.0, max=2.0, step=0.05, display_mode=io.NumberDisplay.slider),
                io.Int.Input("max_tokens", default=-1, min=-1, display_mode=io.NumberDisplay.number),
                io.Combo.Input("reasoning_effort", options=["auto", "off", "low", "medium", "high", "on"], default="auto", tooltip="Controls thinking/reasoning intensity. 'auto' lets the model decide. Will error if model does not support reasoning."),
                io.String.Input("stream_output", multiline=True, default="Waiting for generation..."),
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
    def validate_inputs(cls, **kwargs) -> bool:
        """Bypass strict Combo validation to allow dynamic model lists from the frontend."""
        return True

    @classmethod
    async def execute(
        cls, 
        system_prompt: str,
        prompt: str, 
        connection_mode: dict, 
        model_id: str, 
        json_schema: str,
        seed: int,
        temperature: float, 
        max_tokens: int,
        reasoning_effort: str,
        stream_output: str,
        debug_mode: bool = False,
        image: torch.Tensor | None = None,
        **kwargs
    ) -> io.NodeOutput:

        mode_selected = connection_mode.get("connection_mode", "SDK")
        server_url = connection_mode.get("server_url", "http://localhost:1234")

        node_id = cls.hidden.unique_id
        base64_image = None
        if image is not None:
            base64_image = await asyncio.to_thread(tensor_to_base64, image)

        if debug_mode:
            print(f"[LM Studio Node] Executing with mode={mode_selected}, model={model_id}")

        if mode_selected == "SDK":
            final_text, final_reasoning, stats_str = await LMStudioSDKClient.generate(
                system_prompt=system_prompt,
                model_id=model_id,
                prompt=prompt,
                base64_image=base64_image,
                json_schema=json_schema,
                seed=seed,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                node_id=node_id
            )
        else:
            final_text, final_reasoning, stats_str = await LMStudioRESTClient.generate(
                system_prompt=system_prompt,
                server_url=server_url,
                model_id=model_id,
                prompt=prompt,
                base64_image=base64_image,
                json_schema=json_schema,
                seed=seed,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                node_id=node_id
            )

        return io.NodeOutput(final_text, final_reasoning, stats_str, ui={"stream_output": [final_text]})

class LMStudioExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [LMStudioChatNode]

async def comfy_entrypoint() -> LMStudioExtension:
    return LMStudioExtension()
