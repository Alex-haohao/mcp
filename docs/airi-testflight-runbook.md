# AIRI TestFlight Runbook

This workspace pins AIRI as a Git submodule at `projects/airi`.

The iOS app is AIRI Stage Pocket:

```text
projects/airi/apps/stage-pocket
projects/airi/apps/stage-pocket/ios/App/App.xcodeproj
```

## Current Local Verification

Verified locally on 2026-06-10:

- AIRI submodule cloned at `projects/airi`.
- `pnpm@10.33.0` installed through Corepack.
- `pnpm install --registry=https://registry.npmjs.org/` completed.
- `pnpm -F @proj-airi/stage-pocket build` completed.
- `pnpm -F @proj-airi/stage-pocket exec cap sync ios` completed.
- iOS simulator build completed with signing disabled.
- Xcode account access verified for Team `77NLS6U772`.
- A connected iPhone device build completed and let Xcode create `iOS Team Provisioning Profile: *`.
- Signing diagnostics pass for Team ID, Bundle ID, Apple Development identity, development provisioning profile, Apple Distribution identity, and App Store Connect API key settings.
- iOS Release archive completed at `build/airi-testflight/AIRI.xcarchive`.
- App Store Connect IPA export completed at `build/airi-testflight/export/App.ipa`.
- The workspace build script runs Capacitor sync before native builds and restores the tracked Xcode SPM files changed by sync when they were clean before the build.

Current signed archive and exported IPA:

```text
build/airi-testflight/AIRI.xcarchive
build/airi-testflight/export/App.ipa
```

The current remaining blocker is the App Store Connect app record. A direct upload reached App Store Connect but failed with:

```text
Cannot determine the Apple ID from Bundle ID 'com.tianhaoxi.airi.pocket' and platform 'IOS'. (19)
```

Create an App Store Connect app record for the Bundle ID before retrying TestFlight upload.

## Signing Requirements

TestFlight requires an Apple Developer team, a Bundle ID, local signing identities, provisioning profile access, and an App Store Connect app record.

Current local signing target:

```text
Team ID: 77NLS6U772
Bundle ID: com.tianhaoxi.airi.pocket
```

The local machine has both Apple Development and Apple Distribution identities for the selected team. Xcode 26 may store automatically created provisioning profiles here:

```text
~/Library/Developer/Xcode/UserData/Provisioning Profiles
```

The build script scans both that Xcode directory and the older MobileDevice profile directory.

To finish TestFlight upload, create the App Store Connect app:

1. Open App Store Connect.
2. Go to `Apps`.
3. Create a new iOS app.
4. Select Bundle ID `com.tianhaoxi.airi.pocket`.
5. Set the app name, primary language, and SKU.
6. Save, then rerun the upload command.

Recommended Bundle ID:

```text
com.tianhaoxi.airi.pocket
```

You can choose a different Bundle ID, but use the same value consistently in local builds and App Store Connect.

## Local Configuration

The build script automatically reads this repository's local `.env` file before parsing command-line options. Existing shell environment variables still win over `.env` values.

Useful local keys:

```dotenv
AIRI_IOS_TEAM_ID=77NLS6U772
AIRI_IOS_BUNDLE_ID=com.tianhaoxi.airi.pocket
AIRI_IOS_SIGNING_STYLE=automatic
AIRI_IOS_PROVISIONING_PROFILE=
AIRI_IOS_CODE_SIGN_IDENTITY=
AIRI_ASC_API_KEY_PATH=/Users/<you>/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8
AIRI_ASC_API_KEY_ID=<KEY_ID>
AIRI_ASC_ISSUER_ID=<ISSUER_ID>
```

Keep the `.p8` file outside the repository. The `.env` file is ignored by Git and should remain local.

## Signing Diagnostics

Before attempting a signed archive or upload, run:

```bash
python scripts/airi_ios_testflight.py --diagnose-signing
```

The diagnostic checks:

1. AIRI submodule checkout
2. Team ID and Bundle ID
3. local Apple Development identity
4. local development provisioning profile for the Bundle ID
5. local Apple Distribution identity
6. App Store Connect API key path, key ID, and issuer ID
7. manual provisioning profile when `AIRI_IOS_SIGNING_STYLE=manual`

It does not print secret values and does not contact Apple. For CLI TestFlight upload, every item should be `ok`. If `Development provisioning profile` is missing, open Xcode with the selected Apple Developer team and let automatic signing create a profile for the Bundle ID, or create one in the Apple Developer portal. If `Apple Distribution identity` is missing, refresh the Apple Developer account in Xcode, or create/download the distribution certificate and private key for the selected team. If the ASC API key items are missing, create an App Store Connect API key and put the `.p8` file outside this repository.

## Build Script

The workspace script wraps the verified commands:

```bash
python scripts/airi_ios_testflight.py \
  --team-id 77NLS6U772 \
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
  --team-id 77NLS6U772 \
  --bundle-id com.tianhaoxi.airi.pocket \
  --export-ipa
```

The exported IPA will be under:

```text
build/airi-testflight/export/
```

In automatic signing mode, the script signs the archive with `Apple Development` to avoid AIRI upstream's Release configuration forcing `Apple Distribution` before Xcode has completed automatic provisioning. The App Store Connect export step then performs App Store distribution signing.

To upload with the CLI, create an App Store Connect API key in App Store Connect and provide these values through environment variables or command-line flags:

```bash
export AIRI_ASC_API_KEY_PATH="$HOME/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8"
export AIRI_ASC_API_KEY_ID="<KEY_ID>"
export AIRI_ASC_ISSUER_ID="<ISSUER_ID>"

python scripts/airi_ios_testflight.py \
  --export-ipa \
  --upload-testflight
```

The script never writes App Store Connect secrets into the repository. If upload fails with `Cannot determine the Apple ID from Bundle ID`, the signing/export path is working but App Store Connect does not yet have an app record for that Bundle ID.

If automatic signing remains unreliable, use manual App Store signing:

```bash
python scripts/airi_ios_testflight.py \
  --team-id 77NLS6U772 \
  --bundle-id com.tianhaoxi.airi.pocket \
  --signing-style manual \
  --provisioning-profile "<APP_STORE_PROFILE_NAME_OR_UUID>" \
  --export-ipa \
  --upload-testflight
```

Capacitor sync updates a small set of tracked Xcode SPM files inside the AIRI submodule so Xcode can resolve local Capacitor plugins from `node_modules`. The script restores those files by default after the build so the AIRI submodule stays clean. Use `--keep-synced-xcode-files` only when you want to leave the Xcode project prepared for manual inspection or manual archiving in Xcode.

Avoid `--skip-sync` unless the Xcode project is already prepared from a prior sync. Skipping sync against a restored checkout can make Xcode fail to resolve local Capacitor plugin packages.

After signing is healthy, the signed archive should appear under:

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
