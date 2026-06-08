from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = PROJECT_ROOT / "scripts" / "deploy_server.py"


def load_deploy_module():
    spec = importlib.util.spec_from_file_location("deploy_server_for_tests", DEPLOY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DeployServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deploy = load_deploy_module()

    def test_runtime_env_excludes_deployment_credentials(self):
        text = self.deploy.build_runtime_env(
            {
                "SERVER_IP": "203.0.113.10",
                "SERVER_USERNAME": "root",
                "SERVER_PASSWORD": "secret-password",
                "MCP_ENDPOINT": "wss://example.invalid/mcp",
                "VOLCENGINE_SEARCH_API_KEY": "search-key",
            }
        )

        self.assertIn("MCP_ENDPOINT=", text)
        self.assertIn("VOLCENGINE_SEARCH_API_KEY=", text)
        self.assertNotIn("SERVER_IP", text)
        self.assertNotIn("SERVER_USERNAME", text)
        self.assertNotIn("SERVER_PASSWORD", text)
        self.assertNotIn("secret-password", text)

    def test_runtime_env_requires_current_production_keys(self):
        with self.assertRaisesRegex(RuntimeError, "VOLCENGINE_SEARCH_API_KEY"):
            self.deploy.build_runtime_env({"MCP_ENDPOINT": "wss://example.invalid/mcp"})

    def test_runtime_env_rejects_multiline_values(self):
        with self.assertRaisesRegex(RuntimeError, "single-line"):
            self.deploy.build_runtime_env(
                {
                    "MCP_ENDPOINT": "wss://example.invalid/mcp",
                    "VOLCENGINE_SEARCH_API_KEY": "line1\nline2",
                }
            )


if __name__ == "__main__":
    unittest.main()
