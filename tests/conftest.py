import os
import sys
from unittest.mock import MagicMock

# Mock ComfyUI modules before any real imports happen
sys.modules['server'] = MagicMock()
sys.modules['lmstudio'] = MagicMock()

comfy_api = MagicMock()
comfy_api_latest = MagicMock()

class MockNodeOutput:
    def __init__(self, text, reasoning, stats, ui=None):
        self.text = text
        self.reasoning = reasoning
        self.stats = stats
        self.ui = ui

class MockIO:
    NodeOutput = MockNodeOutput
    class ComfyNode:
        pass
    class Schema:
        pass
    class String:
        Input = MagicMock()
        Output = MagicMock()
    class Image:
        Input = MagicMock()
    class Combo:
        Input = MagicMock()
    class DynamicCombo:
        Input = MagicMock()
        Option = MagicMock()
    class Float:
        Input = MagicMock()
    class Int:
        Input = MagicMock()
    class Boolean:
        Input = MagicMock()
    class Hidden:
        unique_id = MagicMock()
    class ControlAfterGenerate:
        randomize = MagicMock()
    class NumberDisplay:
        slider = MagicMock()
        number = MagicMock()

comfy_api_latest.io = MockIO
comfy_api_latest.ComfyExtension = MagicMock()

sys.modules['comfy_api'] = comfy_api
sys.modules['comfy_api.latest'] = comfy_api_latest

# Add the project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
