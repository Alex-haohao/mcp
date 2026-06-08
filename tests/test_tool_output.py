import unittest
from types import SimpleNamespace

from mcp_bridge.tool_output import tool_result_to_text


class ToolOutputTests(unittest.TestCase):
    def test_tool_result_to_text_extracts_text_content(self):
        result = SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="first"),
                SimpleNamespace(type="text", text="second"),
            ]
        )

        self.assertEqual(tool_result_to_text(result), "first\nsecond")

    def test_tool_result_to_text_falls_back_to_repr_for_unknown_content(self):
        result = SimpleNamespace(content=[{"json": {"ok": True}}])

        self.assertIn("ok", tool_result_to_text(result))


if __name__ == "__main__":
    unittest.main()

