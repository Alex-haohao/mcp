from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "airi_ios_testflight.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("airi_ios_testflight_for_tests", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AiriIosTestFlightScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script_module()

    def test_signed_archive_settings_do_not_blank_identity(self):
        settings = self.script.build_signing_settings(
            team_id="TEAM123456",
            bundle_id="com.example.airi",
            unsigned=False,
        )

        self.assertIn("DEVELOPMENT_TEAM=TEAM123456", settings)
        self.assertIn("PRODUCT_BUNDLE_IDENTIFIER=com.example.airi", settings)
        self.assertIn("CODE_SIGN_STYLE=Automatic", settings)
        self.assertIn("PROVISIONING_PROFILE_SPECIFIER=", settings)
        self.assertNotIn("CODE_SIGN_IDENTITY=", settings)

    def test_unsigned_archive_settings_blank_identity(self):
        settings = self.script.build_signing_settings(
            team_id="TEAM123456",
            bundle_id="com.example.airi",
            unsigned=True,
        )

        self.assertIn("CODE_SIGN_IDENTITY=", settings)


if __name__ == "__main__":
    unittest.main()
