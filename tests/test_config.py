import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_bridge.config import ConfigError, load_bridge_config
from mcp_bridge.secrets import REDACTED, redact_argv, redact_mapping, redact_text


class BridgeConfigTests(unittest.TestCase):
    def write_config(self, payload: dict) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "mcp_config.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_load_bridge_config_expands_env_placeholders(self):
        path = self.write_config(
            {
                "mcpServers": {
                    "volcengine-web-search": {
                        "type": "stdio",
                        "command": "uvx",
                        "args": ["mcp-server-askecho-search-infinity"],
                        "env": {
                            "ASK_ECHO_SEARCH_INFINITY_API_KEY": "${VOLCENGINE_SEARCH_API_KEY}"
                        },
                    }
                }
            }
        )

        config = load_bridge_config(
            path=path,
            environ={"VOLCENGINE_SEARCH_API_KEY": "search-key"},
        )

        server = config.servers["volcengine-web-search"]
        self.assertTrue(server.is_enabled({}))
        self.assertEqual(
            server.env["ASK_ECHO_SEARCH_INFINITY_API_KEY"],
            "search-key",
        )

    def test_load_bridge_config_reports_missing_env_placeholder(self):
        path = self.write_config(
            {
                "mcpServers": {
                    "volcengine-web-search": {
                        "type": "stdio",
                        "command": "uvx",
                        "env": {
                            "ASK_ECHO_SEARCH_INFINITY_API_KEY": "${VOLCENGINE_SEARCH_API_KEY}"
                        },
                    }
                }
            }
        )

        with self.assertRaisesRegex(ConfigError, "VOLCENGINE_SEARCH_API_KEY"):
            load_bridge_config(path=path, environ={})

    def test_explicit_empty_environ_does_not_fall_back_to_process_environment(self):
        path = self.write_config(
            {
                "mcpServers": {
                    "volcengine-web-search": {
                        "type": "stdio",
                        "command": "uvx",
                        "env": {
                            "ASK_ECHO_SEARCH_INFINITY_API_KEY": "${VOLCENGINE_SEARCH_API_KEY}"
                        },
                    }
                }
            }
        )

        with patch.dict(os.environ, {"VOLCENGINE_SEARCH_API_KEY": "ambient-key"}):
            with self.assertRaisesRegex(ConfigError, "VOLCENGINE_SEARCH_API_KEY"):
                load_bridge_config(path=path, environ={})

    def test_enabled_servers_skip_disabled_and_missing_enabled_if_env(self):
        path = self.write_config(
            {
                "mcpServers": {
                    "disabled-server": {
                        "type": "stdio",
                        "command": "python",
                        "disabled": True,
                    },
                    "conditional-server": {
                        "type": "stdio",
                        "command": "uvx",
                        "enabledIfEnv": "VOLCENGINE_SEARCH_API_KEY",
                    },
                    "always-server": {
                        "type": "stdio",
                        "command": "python",
                    },
                }
            }
        )

        config = load_bridge_config(path=path, environ={})

        self.assertEqual(
            [server.name for server in config.enabled_servers({})],
            ["always-server"],
        )
        self.assertEqual(
            [server.name for server in config.enabled_servers({"VOLCENGINE_SEARCH_API_KEY": "key"})],
            ["conditional-server", "always-server"],
        )

    def test_secret_redaction_masks_sensitive_mapping_values_and_text(self):
        redacted = redact_mapping(
            {
                "VOLCENGINE_SEARCH_API_KEY": "search-key",
                "VOLCENGINE_SECRET_KEY": "secret-key",
                "PLAIN_SETTING": "visible",
            }
        )

        self.assertEqual(redacted["VOLCENGINE_SEARCH_API_KEY"], "***REDACTED***")
        self.assertEqual(redacted["VOLCENGINE_SECRET_KEY"], "***REDACTED***")
        self.assertEqual(redacted["PLAIN_SETTING"], "visible")
        self.assertNotIn("search-key", redact_text("failed with api key search-key", ["search-key"]))

    def test_redact_argv_masks_mcp_proxy_sensitive_header_values(self):
        argv = [
            "python",
            "-m",
            "mcp_proxy",
            "-H",
            "Authorization",
            "Bearer secret-token",
            "https://example.com/mcp",
        ]

        self.assertEqual(
            redact_argv(argv),
            [
                "python",
                "-m",
                "mcp_proxy",
                "-H",
                "Authorization",
                REDACTED,
                "https://example.com/mcp",
            ],
        )


if __name__ == "__main__":
    unittest.main()
