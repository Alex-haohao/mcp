import json
import sys
import tempfile
import unittest
from pathlib import Path

from mcp_bridge.config import load_bridge_config
from mcp_bridge.runtime_env import (
    build_child_base_env,
    ensure_executable_available,
    is_executable_available,
)
from mcp_bridge.server_command import build_server_command


class ServerCommandTests(unittest.TestCase):
    def write_config(self, payload: dict) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "mcp_config.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_build_stdio_command_with_resolved_child_environment(self):
        path = self.write_config(
            {
                "mcpServers": {
                    "volcengine-web-search": {
                        "type": "stdio",
                        "command": "uvx",
                        "args": [
                            "--from",
                            "git+https://github.com/volcengine/mcp-server@69d102e079ca74acedd5ec48eeeb24b148efb36e#subdirectory=server/mcp_server_askecho_search_infinity",
                            "mcp-server-askecho-search-infinity",
                        ],
                        "env": {
                            "ASK_ECHO_SEARCH_INFINITY_API_KEY": "${VOLCENGINE_SEARCH_API_KEY}"
                        },
                    }
                }
            }
        )
        config = load_bridge_config(path=path, environ={"VOLCENGINE_SEARCH_API_KEY": "search-key"})

        command = build_server_command(
            "volcengine-web-search",
            config=config,
            base_env={"PATH": "/bin"},
            python_executable="/python",
        )

        self.assertEqual(command.argv[0], "uvx")
        self.assertEqual(command.argv[-1], "mcp-server-askecho-search-infinity")
        self.assertEqual(command.env["PATH"], "/bin")
        self.assertEqual(command.env["ASK_ECHO_SEARCH_INFINITY_API_KEY"], "search-key")

    def test_build_http_command_uses_mcp_proxy_streamable_transport(self):
        path = self.write_config(
            {
                "mcpServers": {
                    "remote-http": {
                        "type": "http",
                        "url": "https://example.com/mcp",
                        "headers": {"Authorization": "Bearer token"},
                    }
                }
            }
        )
        config = load_bridge_config(path=path, environ={})

        command = build_server_command(
            "remote-http",
            config=config,
            base_env={},
            python_executable="/python",
        )

        self.assertEqual(
            command.argv,
            [
                "/python",
                "-m",
                "mcp_proxy",
                "--transport",
                "streamablehttp",
                "-H",
                "Authorization",
                "Bearer token",
                "https://example.com/mcp",
            ],
        )
        self.assertEqual(command.env, {})

    def test_build_command_respects_explicit_empty_base_env(self):
        path = self.write_config(
            {
                "mcpServers": {
                    "local": {
                        "type": "stdio",
                        "command": "python",
                    }
                }
            }
        )
        config = load_bridge_config(path=path, environ={})

        command = build_server_command(
            "local",
            config=config,
            base_env={},
            python_executable="/python",
        )

        self.assertEqual(command.env, {})

    def test_build_script_path_remains_backwards_compatible(self):
        with tempfile.NamedTemporaryFile(suffix=".py") as script:
            command = build_server_command(
                script.name,
                config=load_bridge_config(path=None, environ={}),
                base_env={"PATH": "/bin"},
                python_executable=sys.executable,
            )

        self.assertEqual(command.argv, [sys.executable, script.name])
        self.assertEqual(command.env["PATH"], "/bin")

    def test_child_base_env_prepends_python_bin_to_path(self):
        env = build_child_base_env(
            {"PATH": "/usr/bin"},
            python_executable="/opt/xiaozhi-mcp/.venv/bin/python",
        )

        self.assertEqual(
            env["PATH"],
            "/opt/xiaozhi-mcp/.venv/bin:/usr/bin",
        )

    def test_executable_available_respects_explicit_empty_path(self):
        self.assertFalse(is_executable_available("python", path=""))

        with self.assertRaisesRegex(RuntimeError, "python"):
            ensure_executable_available("python", env={"PATH": ""})


if __name__ == "__main__":
    unittest.main()
