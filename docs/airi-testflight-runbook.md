# AIRI TestFlight Runbook

This workspace pins AIRI as a Git submodule at `projects/airi`.

The iOS app is AIRI Stage Pocket:

```text
projects/airi/apps/stage-pocket
projects/airi/apps/stage-pocket/ios/App/App.xcodeproj
```

## Current Local Verification

Verified locally:

- AIRI submodule cloned at `projects/airi`.
- `pnpm@10.33.0` installed through Corepack.
- `pnpm install --registry=https://registry.npmjs.org/` completed.
- `pnpm -F @proj-airi/stage-pocket build` completed.
- `pnpm -F @proj-airi/stage-pocket exec cap sync ios` completed.
- iOS simulator build completed with signing disabled.
- iOS generic archive completed only when code signing identity was blank, which produces an unsigned archive.
- The workspace build script runs Capacitor sync before native builds and restores the tracked Xcode SPM files changed by sync when they were clean before the build.

Current unsigned archive:

```text
build/airi-testflight/AIRI.xcarchive
```

The unsigned archive proves the app can compile for device, but it cannot be uploaded to TestFlight.

## Signing Requirements

TestFlight requires an App Store signed archive. The current local machine only exposes an Apple Development identity:

```text
Apple Development: ... (KA4786U458)
```

The CLI signed archive with your inferred Team ID currently fails because Xcode cannot complete the App Store distribution signing path. The current observed failure is:

```text
App is automatically signed for development, but a conflicting code signing identity Apple Distribution has been manually specified.
```

Earlier attempts also reported missing account/profile access for Team `KA4786U458`. Treat both as the same external blocker: Xcode needs access to the Apple Developer account, an App ID/provisioning profile for the Bundle ID, and an Apple Distribution signing identity for App Store/TestFlight archives.

To finish TestFlight upload, first open Xcode and complete:

1. `Xcode > Settings > Accounts`
2. Add or refresh your Apple Developer account.
3. Confirm the team ID is available.
4. Create or allow Xcode to create an App ID for your Bundle ID.
5. Ensure Apple Distribution signing is available for App Store/TestFlight upload.

Recommended Bundle ID:

```text
com.tianhaoxi.airi.pocket
```

You can choose a different Bundle ID, but use the same value consistently in local builds and App Store Connect.

## Local Configuration

The build script automatically reads this repository's local `.env` file before parsing command-line options. Existing shell environment variables still win over `.env` values.

Useful local keys:

```dotenv
AIRI_IOS_TEAM_ID=KA4786U458
AIRI_IOS_BUNDLE_ID=com.tianhaoxi.airi.pocket
AIRI_IOS_SIGNING_STYLE=automatic
AIRI_IOS_PROVISIONING_PROFILE=
AIRI_IOS_CODE_SIGN_IDENTITY=
AIRI_ASC_API_KEY_PATH=/Users/<you>/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8
AIRI_ASC_API_KEY_ID=<KEY_ID>
AIRI_ASC_ISSUER_ID=<ISSUER_ID>
```

Keep the `.p8` file outside the repository. The `.env` file is ignored by Git and should remain local.

## Build Script

The workspace script wraps the verified commands:

```bash
python scripts/airi_ios_testflight.py \
  --team-id KA4786U458 \
  --bundle-id com.tianhaoxi.airi.pocket
```

The script runs:

1. `pnpm install`
2. Stage Pocket production build
3. Capacitor iOS sync
4. iOS simulator compile smoke test
5. iOS Release archive for generic device

By default this creates a signed archive only. Add `--export-ipa` after signing is healthy to produce an App Store Connect IPA:

```bash
python scripts/airi_ios_testflight.py \
  --team-id KA4786U458 \
  --bundle-id com.tianhaoxi.airi.pocket \
  --export-ipa
```

The exported IPA will be under:

```text
build/airi-testflight/export/
```

To upload with the CLI, create an App Store Connect API key in App Store Connect and provide these values through environment variables or command-line flags:

```bash
export AIRI_ASC_API_KEY_PATH="$HOME/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8"
export AIRI_ASC_API_KEY_ID="<KEY_ID>"
export AIRI_ASC_ISSUER_ID="<ISSUER_ID>"

python scripts/airi_ios_testflight.py \
  --export-ipa \
  --upload-testflight
```

The script never writes App Store Connect secrets into the repository.

If automatic signing remains unreliable, use manual App Store signing:

```bash
python scripts/airi_ios_testflight.py \
  --team-id KA4786U458 \
  --bundle-id com.tianhaoxi.airi.pocket \
  --signing-style manual \
  --provisioning-profile "<APP_STORE_PROFILE_NAME_OR_UUID>" \
  --export-ipa \
  --upload-testflight
```

Capacitor sync updates a small set of tracked Xcode SPM files inside the AIRI submodule so Xcode can resolve local Capacitor plugins from `node_modules`. The script restores those files by default after the build so the AIRI submodule stays clean. Use `--keep-synced-xcode-files` only when you want to leave the Xcode project prepared for manual inspection or manual archiving in Xcode.

Avoid `--skip-sync` unless the Xcode project is already prepared from a prior sync. Skipping sync against a restored checkout can make Xcode fail to resolve local Capacitor plugin packages.

After Xcode account/signing is fixed, the signed archive should appear under:

```text
build/airi-testflight/AIRI.xcarchive
```

## Upload

The most reliable first upload path is Xcode Organizer:

1. Open `projects/airi/apps/stage-pocket/ios/App/App.xcodeproj`.
2. Select the `App` scheme.
3. Select `Any iOS Device`.
4. `Product > Archive`.
5. In Organizer, choose `Distribute App`.
6. Select `App Store Connect`.
7. Upload to TestFlight.
