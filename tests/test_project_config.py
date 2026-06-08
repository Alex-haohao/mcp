from pathlib import Path
import unittest

from mcp_bridge.config import load_bridge_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProjectConfigTests(unittest.TestCase):
    def test_weibo_server_is_pinned_and_enabled_by_default(self):
        config = load_bridge_config(PROJECT_ROOT / "mcp_config.json", environ={})
        server = config.servers["weibo"]

        self.assertTrue(server.is_enabled({}))
        self.assertEqual(server.command, "uvx")
        self.assertEqual(
            server.args,
            ["--from", "mcp-server-weibo==1.1.0", "mcp-server-weibo", "stdio"],
        )

    def test_xiaohongshu_server_requires_url_and_exposes_only_read_tools(self):
        config = load_bridge_config(PROJECT_ROOT / "mcp_config.json", environ={})
        server = config.servers["xiaohongshu-mcp"]

        self.assertFalse(server.is_enabled({}))
        self.assertTrue(
            server.is_enabled({"XIAOHONGSHU_MCP_URL": "http://127.0.0.1:18060/mcp"})
        )
        self.assertEqual(
            server.allowedTools,
            [
                "check_login_status",
                "list_feeds",
                "search_feeds",
                "get_feed_detail",
                "user_profile",
            ],
        )
        self.assertNotIn("publish_content", server.allowedTools)
        self.assertNotIn("post_comment_to_feed", server.allowedTools)
        self.assertNotIn("like_feed", server.allowedTools)


if __name__ == "__main__":
    unittest.main()

