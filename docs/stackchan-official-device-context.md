# StackChan Official Device Context

Last reviewed: 2026-06-30

This runbook records the official M5Stack StackChan context needed before integrating our custom image pack into firmware.

## Sources Checked

- M5Stack product documentation: https://docs.m5stack.com/en/StackChan
- M5Stack Arduino image-files example: https://docs.m5stack.com/en/arduino/stackchan/pic
- M5Stack StackChan open-source repo, reviewed at `0286f72`: https://github.com/m5stack/StackChan/tree/0286f72
- M5Stack StackChan-BSP Arduino library, reviewed at `f7ed40e`: https://github.com/m5stack/StackChan-BSP/tree/f7ed40e
- Current generated pack in this repo: `workspace/stackchan-image-packs/img4635-hatch-pet-stackchan-20260630/final/manifest.json`

The official StackChan repo says open-source updates can lag released factory firmware and mobile app. Treat source analysis as the best implementation map, but verify behavior on the device before assuming it exactly matches the current production firmware.

## Device Facts

The product is the M5Stack StackChan SKU K151 built around CoreS3.

Key constraints for avatar work:

- Main controller: CoreS3 / ESP32-S3, 240 MHz dual core.
- Memory: 16 MB Flash, 8 MB PSRAM.
- Display: CoreS3 2.0-inch capacitive touch display, treated by firmware as a 320x240 LVGL canvas.
- I/O available on the product: camera, mic, speaker, IMU, proximity/light sensor, microSD, Wi-Fi, BLE, servos, RGB LEDs, IR, touch panel, NFC.
- Factory firmware includes AI Agent, expressive animations, ESP-NOW remote control, app downloads, mobile app video viewing, remote avatar control, and OTA.

Implication: the custom avatar must preserve the official firmware behavior. A standalone Arduino sketch can prove that images display, but it is not the production integration path if we want to keep AI Agent, app control, OTA, WebSocket/BLE control, motion, speech, and decorators.

## Official Firmware Shape

The official source is an ESP-IDF firmware plus mobile app plus server:

- `firmware/`: device firmware.
- `app/`: StackChan mobile app.
- `server/`: backend and WebSocket bridge.
- `remote/`: ESP-NOW remote control firmware.

The Avatar app installs `avatar::DefaultAvatar` and wires BLE/WebSocket avatar control into `GetStackChan().updateAvatarFromJson(...)`:

- `firmware/main/apps/app_avatar/app_avatar.cpp`
- `AppAvatar::onOpen()` creates `DefaultAvatar`.
- `onWsAvatarData` calls `GetStackChan().updateAvatarFromJson(data.data())`.

The remote-control app also attaches `DefaultAvatar` and then adds modifiers:

- `firmware/main/apps/app_espnow_ctrl/app_espnow_ctrl.cpp`

The core avatar model is semantic, not image-sheet based:

- `firmware/main/stackchan/avatar/avatar/avatar.h`
- `firmware/main/stackchan/avatar/avatar/elements/emotion.h`
- `firmware/main/stackchan/avatar/avatar/elements/feature.h`

Official `Emotion` values:

```text
Neutral
Happy
Angry
Sad
Doubt
Sleepy
```

This exactly matches our image-pack skill contract:

```text
neutral
happy
angry
sad
doubt
sleepy
```

Official `Feature` inputs are normalized values:

- `weight`: 0..100
- `size`: -100..100
- `position`: normalized in `Element`
- `rotation`: normalized LVGL rotation units
- `visible`: on/off

The existing `DefaultAvatar` uses these values to draw LVGL shapes. Our `ImageAvatar` should keep the same semantic inputs and map them to sprite frames and transforms.

## Rendering And Asset Facts

The current official `DefaultAvatar` creates a 320x240 panel:

- `firmware/main/stackchan/avatar/skins/default/default.cpp`
- `_pannel->setSize(320, 240)`

`DefaultEyes` and `DefaultMouth` show the intended mapping behavior:

- Eyes are centered around `(-70, -16)` and `(70, -16)` relative to screen center.
- Mouth is centered around `(0, 26)` relative to screen center.
- Eyes use `setEmotion()` to change weight and rotation.
- Mouth uses `setWeight()` to map speech intensity into shape size.

Our generated pack currently uses explicit anchors:

```json
{
  "leftEye": { "x": 140, "y": 84 },
  "rightEye": { "x": 180, "y": 84 },
  "mouth": { "x": 160, "y": 109 }
}
```

This is consistent with the official face being centered on a 320x240 panel. The first firmware pass should use manifest anchors directly, then adjust after device screenshots if needed.

The firmware has a 4 MB `assets` SPIFFS partition:

```text
assets, data, spiffs, 0xA00000, 4M
```

The build system supports three relevant asset modes:

- flash generated default assets;
- flash a custom assets file via `CONFIG_FLASH_CUSTOM_ASSETS` and `CONFIG_CUSTOM_ASSETS_FILE`;
- build expression assets for the alternate emote message style.

The firmware asset helper can produce an LVGL image descriptor from:

- `.bin`: pre-converted LVGL image binary with header;
- `.png`, `.jpg`, `.jpeg`, `.gif`: encoded standard image data.

Best practice for our core face parts remains preconverted LVGL descriptors or `.bin` assets, not runtime PNG/GIF decode for every expression update. Encoded PNGs are acceptable for early bring-up if benchmarked, but production should avoid decode overhead and frame-time variance.

## Current Image Pack State

Current accepted generated pack:

```text
workspace/stackchan-image-packs/img4635-hatch-pet-stackchan-20260630/
```

Important outputs:

```text
final/manifest.json
final/body/base.png
final/concepts/{neutral,happy,angry,sad,doubt,sleepy}.png
final/eyes/**/*
final/mouth/**/*
final/decorators/{heart,sweat,anger,tear,dizzy}.png
qa/contact-sheet.png
qa/previews/{neutral,happy,angry,sad,doubt,sleepy}.gif
qa/validation.json
img4635-hatch-pet-stackchan-final.zip
```

Validation status:

```json
{
  "ok": true,
  "errors": [],
  "warnings": []
}
```

Size snapshot:

```text
final/      908K
qa/         2.2M
final zip   676K
```

The runtime pack contract is:

- canvas: 320x240;
- eye frame: 48x48;
- eye strip: 4 frames per side per emotion;
- mouth frame: 96x48;
- mouth strip: 4 frames per emotion;
- emotions: 6;
- decorators: 5.

This conservative component-sprite contract is a good fit for the official firmware because the firmware already uses normalized `Feature` values. Do not move to high-count full-screen frame swaps until a device benchmark proves the need and budget.

## Arduino Position

Arduino can be used, but only for bring-up or asset inspection.

Useful Arduino tasks:

- verify that the CoreS3 display and microSD image loading work;
- preview PNG appearance on the physical 320x240 panel;
- quickly check color, contrast, and scale before firmware integration;
- test generated static images without touching official firmware.

Not recommended as final path:

- replacing the factory firmware with an Arduino sketch;
- re-implementing AI Agent, app control, OTA, WebSocket/BLE avatar control, motion, speech, and decorators;
- building a one-off full-screen PNG/GIF player.

The production path should remain official ESP-IDF firmware plus a new image-based avatar skin.

## Recommended Architecture

Add an image skin beside the official default skin:

```text
firmware/main/stackchan/avatar/skins/image/
```

The first version should add:

- pure frame-mapping helpers, host-testable without LVGL;
- a manifest-derived or generated pack descriptor;
- `ImageSpriteFeature` for eyes and mouth;
- `ImageAvatar` as an `Avatar` implementation parallel to `DefaultAvatar`;
- Kconfig switch to choose default vs image skin;
- narrow hook in `AppAvatar::onOpen()` and ESP-NOW control app if needed.

Do not change the public JSON control shape first. Existing mobile app and server control should continue to work through:

```text
ControlAvatar -> onWsAvatarData -> updateAvatarFromJson -> Feature / Emotion updates
```

The server WebSocket protocol already reserves `0x03` for `ControlAvatar`, so MCP/service-side expression control can come later without changing the first firmware skin.

## Quality And Frame Budget

Use the current 4-frame component pack for the first device test.

Rationale:

- Full-screen 320x240 RGB565 is 153,600 bytes before descriptor/header overhead.
- Six emotions times multiple full-screen frames would quickly compete with the 4 MB assets partition and OTA/app partition constraints.
- Component sprites allow eye/mouth motion without redrawing the entire character as many full frames.
- The official firmware exposes continuous `weight` values, so firmware can quantize those into 4 component frames now and 6-7 frames later if needed.

Upgrade path only after smoke testing:

- mouth: 4 -> 6 frames if speech looks too coarse;
- blink/eyes: 4 -> 6 or 7 frames if popping is visible;
- body: keep one base layer unless idle body motion is proven necessary;
- full-screen expression frames: use only for special transitions, not the default live face.

## Immediate Next Steps

1. Prepare the official firmware checkout.

```bash
mkdir -p /Users/tianhaoxi/project
git clone https://github.com/m5stack/StackChan.git /Users/tianhaoxi/project/StackChan
cd /Users/tianhaoxi/project/StackChan
git checkout -b codex/image-avatar
```

If the repo already exists, fetch and fast-forward `main` first, then create or reset the feature branch intentionally.

2. Fetch official firmware dependencies and run baseline host tests.

```bash
cd /Users/tianhaoxi/project/StackChan/firmware
python3 ./fetch_repos.py
cmake -S tests -B build-host-tests
cmake --build build-host-tests
ctest --test-dir build-host-tests --output-on-failure
```

3. Build the pure mapping layer first.

Add host-tested logic for:

- emotion enum to manifest emotion key;
- `weight 0..100` to sprite frame index;
- normalized position to pixel offset;
- optional size/rotation passthrough policy.

4. Convert the accepted pack into firmware assets.

Use the current final pack as the source:

```text
/Users/tianhaoxi/project/mcp/workspace/stackchan-image-packs/img4635-hatch-pet-stackchan-20260630/final
```

Create a firmware staging directory that can later become custom `assets.bin` content or generated LVGL descriptors.

5. Add the first `ImageAvatar` skin.

Keep it narrow:

- one 320x240 body image;
- left/right eye image objects;
- one mouth image object;
- per-emotion frame arrays;
- frame index selected by current `weight`;
- anchors from `manifest.json`.

6. Hook it behind Kconfig.

Default should remain official `DefaultAvatar`. Add a build-time option such as:

```text
CONFIG_STACKCHAN_AVATAR_SKIN_DEFAULT
CONFIG_STACKCHAN_AVATAR_SKIN_IMAGE
```

7. Build, flash, and smoke-test on hardware.

Minimum acceptance:

- boots without crash;
- Avatar app opens;
- neutral face displays correctly;
- blink modifier changes eye frames;
- speech/speaking changes mouth frames;
- app/WebSocket/BLE avatar control still changes emotion;
- close/reopen path does not leak or leave hidden LVGL objects;
- OTA/server/app features are not broken by the skin switch.

8. Feed device findings back into this repo.

Update:

- `docs/stackchan-image-pack-generation-skill.md`;
- `docs/superpowers/plans/2026-06-30-stackchan-image-avatar.md`;
- `skills/stackchan-image-pack/SKILL.md` if asset dimensions, frame counts, or conversion rules change.

## Current Decision

The next engineering step is not more image generation. The next step is official firmware bring-up:

```text
official checkout -> baseline tests -> ImageAvatar mapping test -> asset conversion -> firmware skin -> device smoke test
```

Only generate more frames or new art after device screenshots show a specific problem.
