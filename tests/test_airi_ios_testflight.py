from __future__ import annotations

import importlib.util
import os
import tempfile
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
        self.assertIn("CODE_SIGN_IDENTITY=Apple Development", settings)
        self.assertNotIn("CODE_SIGN_IDENTITY=", settings)

    def test_unsigned_archive_settings_blank_identity(self):
        settings = self.script.build_signing_settings(
            team_id="TEAM123456",
            bundle_id="com.example.airi",
            unsigned=True,
        )

        self.assertIn("CODE_SIGN_IDENTITY=", settings)

    def test_parse_dotenv_line_supports_quotes_and_comments(self):
        self.assertEqual(
            self.script.parse_dotenv_line("AIRI_IOS_TEAM_ID=KA4786U458"),
            ("AIRI_IOS_TEAM_ID", "KA4786U458"),
        )
        self.assertEqual(
            self.script.parse_dotenv_line('AIRI_ASC_API_KEY_PATH="~/keys/AuthKey_ABC.p8"'),
            ("AIRI_ASC_API_KEY_PATH", "~/keys/AuthKey_ABC.p8"),
        )
        self.assertEqual(
            self.script.parse_dotenv_line("export AIRI_IOS_BUNDLE_ID=com.example.airi # local"),
            ("AIRI_IOS_BUNDLE_ID", "com.example.airi"),
        )
        self.assertIsNone(self.script.parse_dotenv_line("# comment"))

    def test_load_dotenv_does_not_override_existing_environment(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "AIRI_IOS_TEAM_ID=FROM_FILE",
                        "AIRI_IOS_BUNDLE_ID=com.example.airi",
                    ]
                ),
                encoding="utf-8",
            )

            original_team = os.environ.get("AIRI_IOS_TEAM_ID")
            original_bundle = os.environ.get("AIRI_IOS_BUNDLE_ID")
            try:
                os.environ["AIRI_IOS_TEAM_ID"] = "FROM_ENV"
                os.environ.pop("AIRI_IOS_BUNDLE_ID", None)

                self.script.load_dotenv(env_path)

                self.assertEqual(os.environ["AIRI_IOS_TEAM_ID"], "FROM_ENV")
                self.assertEqual(os.environ["AIRI_IOS_BUNDLE_ID"], "com.example.airi")
            finally:
                if original_team is None:
                    os.environ.pop("AIRI_IOS_TEAM_ID", None)
                else:
                    os.environ["AIRI_IOS_TEAM_ID"] = original_team
                if original_bundle is None:
                    os.environ.pop("AIRI_IOS_BUNDLE_ID", None)
                else:
                    os.environ["AIRI_IOS_BUNDLE_ID"] = original_bundle

    def test_manual_signed_archive_settings_require_profile(self):
        with self.assertRaisesRegex(RuntimeError, "provisioning-profile"):
            self.script.build_signing_settings(
                team_id="TEAM123456",
                bundle_id="com.example.airi",
                unsigned=False,
                signing_style="manual",
            )

    def test_manual_signed_archive_uses_distribution_identity(self):
        settings = self.script.build_signing_settings(
            team_id="TEAM123456",
            bundle_id="com.example.airi",
            unsigned=False,
            signing_style="manual",
            provisioning_profile="AIRI App Store",
        )

        self.assertIn("CODE_SIGN_STYLE=Manual", settings)
        self.assertIn("PROVISIONING_PROFILE_SPECIFIER=AIRI App Store", settings)
        self.assertIn("CODE_SIGN_IDENTITY=Apple Distribution", settings)

    def test_authentication_args_are_all_or_nothing(self):
        with self.assertRaisesRegex(RuntimeError, "requires key path"):
            self.script.build_authentication_args(
                key_path="/tmp/AuthKey_ABC123.p8",
                key_id="ABC123",
                issuer_id=None,
            )

        args = self.script.build_authentication_args(
            key_path="~/private_keys/AuthKey_ABC123.p8",
            key_id="ABC123",
            issuer_id="issuer-uuid",
        )

        self.assertEqual(
            args,
            [
                "-authenticationKeyPath",
                str(Path("~/private_keys/AuthKey_ABC123.p8").expanduser()),
                "-authenticationKeyID",
                "ABC123",
                "-authenticationKeyIssuerID",
                "issuer-uuid",
            ],
        )

    def test_export_options_for_automatic_app_store_connect(self):
        options = self.script.build_export_options(
            team_id="TEAM123456",
            bundle_id="com.example.airi",
            signing_style="automatic",
            provisioning_profile=None,
        )

        self.assertEqual(options["method"], "app-store-connect")
        self.assertEqual(options["destination"], "export")
        self.assertEqual(options["teamID"], "TEAM123456")
        self.assertEqual(options["signingStyle"], "automatic")
        self.assertNotIn("provisioningProfiles", options)

    def test_export_options_for_manual_profile(self):
        options = self.script.build_export_options(
            team_id="TEAM123456",
            bundle_id="com.example.airi",
            signing_style="manual",
            provisioning_profile="AIRI App Store",
            internal_testing_only=True,
        )

        self.assertEqual(
            options["provisioningProfiles"],
            {"com.example.airi": "AIRI App Store"},
        )
        self.assertTrue(options["testFlightInternalTestingOnly"])

    def test_write_export_options_writes_plist(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            original_build_dir = self.script.BUILD_DIR
            original_export_options_path = self.script.EXPORT_OPTIONS_PATH
            try:
                self.script.BUILD_DIR = Path(tmp_dir)
                self.script.EXPORT_OPTIONS_PATH = Path(tmp_dir) / "ExportOptions.plist"

                self.script.write_export_options({"method": "app-store-connect"})

                self.assertTrue(self.script.EXPORT_OPTIONS_PATH.exists())
            finally:
                self.script.BUILD_DIR = original_build_dir
                self.script.EXPORT_OPTIONS_PATH = original_export_options_path

    def test_upload_requires_app_store_connect_authentication(self):
        with self.assertRaisesRegex(RuntimeError, "TestFlight upload requires"):
            self.script.require_app_store_connect_authentication(
                key_path=None,
                key_id=None,
                issuer_id=None,
            )

    def test_collect_code_signing_identity_names(self):
        output = """
  1) ABCDEF "Apple Development: Example (TEAM123456)"
  2) 123456 "Apple Distribution: Example, Inc. (TEAM123456)"
     2 valid identities found
"""

        self.assertEqual(
            self.script.collect_code_signing_identity_names(output),
            [
                "Apple Development: Example (TEAM123456)",
                "Apple Distribution: Example, Inc. (TEAM123456)",
            ],
        )

    def test_build_signing_diagnostics_reports_missing_upload_assets(self):
        diagnostics = self.script.build_signing_diagnostics(
            team_id=None,
            bundle_id=None,
            signing_style="automatic",
            provisioning_profile=None,
            key_path=None,
            key_id=None,
            issuer_id=None,
            identity_names=["Apple Development: Example (TEAM123456)"],
            development_profile_names=[],
        )
        by_label = {label: ok for label, ok, _ in diagnostics}

        self.assertFalse(by_label["Team ID"])
        self.assertFalse(by_label["Bundle ID"])
        self.assertTrue(by_label["Apple Development identity"])
        self.assertFalse(by_label["Development provisioning profile"])
        self.assertFalse(by_label["Apple Distribution identity"])
        self.assertFalse(by_label["ASC API key path"])

    def test_build_signing_diagnostics_accepts_complete_cli_upload_assets(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            key_path = Path(tmp_dir) / "AuthKey_ABC123.p8"
            key_path.write_text("private-key-placeholder", encoding="utf-8")

            diagnostics = self.script.build_signing_diagnostics(
                team_id="TEAM123456",
                bundle_id="com.example.airi",
                signing_style="automatic",
                provisioning_profile=None,
                key_path=str(key_path),
                key_id="ABC123",
                issuer_id="issuer-uuid",
                identity_names=[
                    "Apple Development: Example (TEAM123456)",
                    "Apple Distribution: Example, Inc. (TEAM123456)",
                ],
                development_profile_names=["AIRI Development"],
            )

        self.assertTrue(all(ok for _, ok, _ in diagnostics))

    def test_profile_matches_exact_development_bundle(self):
        profile = {
            "TeamIdentifier": ["TEAM123456"],
            "Entitlements": {
                "application-identifier": "TEAM123456.com.example.airi",
                "get-task-allow": True,
            },
        }

        self.assertTrue(
            self.script.profile_matches_bundle(
                profile,
                team_id="TEAM123456",
                bundle_id="com.example.airi",
                development=True,
            )
        )

    def test_profile_rejects_distribution_when_development_required(self):
        profile = {
            "TeamIdentifier": ["TEAM123456"],
            "Entitlements": {
                "application-identifier": "TEAM123456.com.example.airi",
                "get-task-allow": False,
            },
        }

        self.assertFalse(
            self.script.profile_matches_bundle(
                profile,
                team_id="TEAM123456",
                bundle_id="com.example.airi",
                development=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
