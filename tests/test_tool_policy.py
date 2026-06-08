import json
import unittest

from mcp_bridge.config import McpServerConfig
from mcp_bridge.tool_policy import ToolPolicy


class ToolPolicyTests(unittest.TestCase):
    def test_filters_list_tools_response_to_allowed_tools(self):
        policy = ToolPolicy.from_server(
            McpServerConfig(
                name="xiaohongshu-mcp",
                allowedTools=["check_login_status", "search_feeds"],
            )
        )
        message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "tools": [
                        {"name": "check_login_status"},
                        {"name": "publish_content"},
                        {"name": "search_feeds"},
                    ]
                },
            }
        )

        filtered = json.loads(policy.filter_process_message(message))

        self.assertEqual(
            [tool["name"] for tool in filtered["result"]["tools"]],
            ["check_login_status", "search_feeds"],
        )

    def test_blocks_disallowed_tool_call_before_child_process(self):
        policy = ToolPolicy.from_server(
            McpServerConfig(
                name="xiaohongshu-mcp",
                allowedTools=["check_login_status", "search_feeds"],
            )
        )
        message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "publish_content", "arguments": {}},
            }
        )

        response = json.loads(policy.blocked_request_response(message))

        self.assertEqual(response["id"], 5)
        self.assertEqual(response["error"]["code"], -32001)
        self.assertIn("publish_content", response["error"]["message"])

    def test_allows_configured_tool_call(self):
        policy = ToolPolicy.from_server(
            McpServerConfig(name="xiaohongshu-mcp", allowedTools=["search_feeds"])
        )
        message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "search_feeds", "arguments": {}},
            }
        )

        self.assertIsNone(policy.blocked_request_response(message))

    def test_policy_is_inactive_without_allow_or_block_lists(self):
        policy = ToolPolicy.from_server(McpServerConfig(name="weibo"))
        message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"tools": [{"name": "a"}, {"name": "b"}]},
            }
        )

        self.assertEqual(policy.filter_process_message(message), message)
        self.assertIsNone(
            policy.blocked_request_response(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 7,
                        "method": "tools/call",
                        "params": {"name": "anything"},
                    }
                )
            )
        )


if __name__ == "__main__":
    unittest.main()

