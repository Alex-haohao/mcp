# StackChan Official Device Context

Last reviewed: 2026-06-30

This runbook records the official M5Stack StackChan context needed before integrating our custom image pack into firmware.

## Sources Checked

- M5Stack product documentation: https://docs.m5stack.com/en/StackChan
- M5Stack Arduino image-files example: https://docs.m5stack.com/en/arduino/stackchan/pic
- M5Stack StackChan open-source repo, reviewed at `0286f72`: https://github.com/m5stack/StackChan/tree/0286f72
- Local writable fork submodule: `projects/StackChan`, fork URL https://github.com/Alex-haohao/StackChan
- Current local setup branch: `codex/image-avatar` at `4ce404a`, based on official `0286f72` plus ImageAvatar implementation and ESP-IDF build-verification commits.
- M5Stack StackChan-BSP Arduino library, reviewed at `f7ed40e`: https://github.com/m5stack/StackChan-BSP/tree/f7ed40e
- Current generated pack in this repo: `workspace/stackchan-image-packs/img4635-hatch-pet-stackchan-20260630/final/manifest.json`

The official StackChan repo says open-source updates can lag released factory firmware and mobile app. Treat source analysis as the best implementation map, but verify behavior on the device before assuming it exactly matches the current production firmware.

## Workspace Location

StackChan is prepared inside the current AI workspace as a fork-backed git submodule:

```text
/Users/tianhaoxi/project/mcp/projects/StackChan
```

Tracked submodule remote:

```text
https://github.com/Alex-haohao/StackChan.git
```

Local working remotes should be:

```text
origin   https://github.com/Alex-haohao/StackChan.git
upstream https://github.com/m5stack/StackChan.git
```

Use `origin` for branches and pushes. Use `upstream` only for reading official updates; its push URL should stay disabled locally.

## Local ESP-IDF Environment

ESP-IDF v5.5.4 is installed locally for StackChan/CoreS3 work:

```text
/Users/tianhaoxi/esp/esp-idf-v5.5.4
```

Espressif tools and Python packages are installed under the default tools path:

```text
/Users/tianhaoxi/.espressif
```

The interactive zsh entrypoint is:

```bash
get_idf
```

This alias sources:

```bash
$HOME/esp/esp-idf-v5.5.4/export.sh
```

Verified tool versions on 2026-06-30:

```text
ESP-IDF v5.5.4
xtensa-esp-elf-gcc 14.2.0
ninja 1.13.2
dfu-util 0.11
```

Keep ESP-IDF opt-in through `get_idf` instead of auto-sourcing it from every
shell. This avoids changing PATH and Python behavior for unrelated projects.

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

## Local Firmware Build Results

The current fork branch has been verified with ESP-IDF v5.5.4 on 2026-06-30.

Default official avatar build:

```text
stack-chan.bin size: 0x39adc0
smallest app partition: 0x4f0000
free: 0x155240 bytes, 27%
```

ImageAvatar build with `sdkconfig.defaults.local` overlay:

```text
stack-chan.bin size: 0x476b80
smallest app partition: 0x4f0000
free: 0x079480 bytes, 10%
```

Host tests:

```text
motion_math_test passed
image_avatar_mapping_test passed
```

The ImageAvatar build fits but leaves only about 10% free in the app partition.
Future image-pack iterations should avoid full-screen animation frames and must
check `idf.py build` size output after every asset update.

## Current Image Pack State

Current generated pack under visual review:

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

Important: structural validation is not release acceptance. An earlier device review after flashing showed that the body proportions were roughly correct, but eyes and mouth had unacceptable placement/proportion. The source-level diagnosis indicated this was primarily an image-pack QA failure, not an LVGL descriptor or general firmware coordinate failure:

- source body is 320x240 and centered;
- eye and mouth PNG frames use the expected dimensions and are internally centered;
- broken manifest anchors were `leftEye=(140,84)`, `rightEye=(180,84)`, `mouth=(160,109)`;
- firmware converted those to screen-center offsets `(-20,-36)`, `(20,-36)`, `(0,-11)`;
- source-level overlay already shows eyes too high/close and mouth too high/small;
- neutral closed mouth content is about `21x7` inside a 96x48 frame, making it weak at 320x240 device scale.

Current IMG4635 status:

- the previous face-layout repair route is rejected as a reusable workflow;
- do not use local scripts to redraw, resize, reconstruct, or recenter eyes or mouth;
- postprocess must run in upstream-preserving mode: chroma-key removal plus whole-canvas/whole-strip normalization only;
- the next accepted pack must regenerate bad eye/mouth components upstream with `$imagegen`, grounded by canonical style, body base, matching emotion concept, strip guide, and face-proportion guide;
- firmware offsets/descriptors should be derived only after source-level semantic-fit, anchor-fit, motion-sheet, contact-sheet, and preview QA pass.

Durable rule: do not treat manifest/descriptor validity as visual acceptance. Before regenerating LVGL descriptors or flashing a new pack, run the image-pack semantic-fit and anchor-fit diagnostics and inspect:

```text
qa/semantic-fit/semantic-fit-report.json
qa/semantic-fit/neutral-semantic-overlay.png
qa/postprocess-summary.json
qa/motion-sheet.png
qa/anchor-fit/anchor-fit-report.json
qa/anchor-fit/neutral-concept-vs-overlay.png
qa/anchor-fit/neutral-manifest-overlay.png
```

Only change firmware placement constants after the source manifest and generated overlays are accepted. If overlays are wrong, repair the manifest anchors or the source eye/mouth strips and rerun the full deterministic QA chain.

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

## Current Firmware Integration State

Implemented in the `projects/StackChan` submodule on branch `codex/image-avatar`:

- commit `981ff8b`: host-tested ImageAvatar mapping helpers;
- commit `834b27f`: optional ImageAvatar skin, complete generated pack assets, Kconfig wiring, and firmware-local docs;
- `CONFIG_STACKCHAN_AVATAR_SKIN_DEFAULT` remains the default;
- `CONFIG_STACKCHAN_AVATAR_SKIN_IMAGE` enables the generated image skin in the Avatar app;
- official `Avatar`, `Feature`, JSON control, HAL, app/server protocol, and `DefaultAvatar` remain unchanged.

The image skin is additive under:

```text
firmware/main/stackchan/avatar/skins/image/
```

The generated LVGL descriptors are under:

```text
firmware/main/stackchan/avatar/skins/image/packs/assets/
```

Current generated firmware asset footprint:

```text
73 LVGL RGB565A8 descriptor files
5.7M generated C source under packs/assets
```

Frame mapping notes:

- body uses one shared 320x240 base layer;
- expression changes swap eye and mouth frame arrays;
- eye frames are generated open-to-closed, so eye weight mapping is reversed to preserve official semantics where `weight=100` means open;
- mouth frames are generated closed-to-open, so mouth weight mapping is direct;
- anchors from the accepted `manifest.json` are converted to screen-center offsets by `firmware/tools/sync_image_avatar_pack.py`: left eye `(-24, -38)`, right eye `(22, -38)`, mouth `(-2, -11)`.

Verification completed locally:

```text
cmake --build build-host-tests
ctest --test-dir build-host-tests --output-on-failure
git diff --check
temporary fake-LVGL syntax check for pack descriptors and representative assets
preprocessor asset-reference check: 73 referenced, 0 missing, 0 unused
validate_stackchan_pack.py
diagnose_stackchan_semantic_fit.py
diagnose_stackchan_anchor_fit.py
make_stackchan_motion_sheet.py
render_stackchan_motion_previews.py
idf.py build
idf.py -p /dev/cu.usbmodem101 flash
idf.py -p /dev/cu.usbmodem101 monitor boot smoke
```

Verification still pending after the current flash:

```text
human visual check on physical screen after opening Avatar
device smoke test with default skin if switching back to default config
official app/WebSocket/BLE avatar-control smoke test
```

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

The current first version adds:

- pure frame-mapping helpers, host-testable without LVGL;
- a manifest-derived or generated pack descriptor;
- `ImageSpriteFeature` for eyes and mouth;
- `ImageAvatar` as an `Avatar` implementation parallel to `DefaultAvatar`;
- Kconfig switch to choose default vs image skin;
- narrow hook in `AppAvatar::onOpen()`.

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

1. Install or source ESP-IDF v5.5.x.

```bash
idf.py --version
```

Expected: `ESP-IDF v5.5.x`. Current environment result: `idf.py` is not found.

2. Build the firmware with the default avatar selected.

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
idf.py build
```

Expected: build succeeds with `CONFIG_STACKCHAN_AVATAR_SKIN_DEFAULT`.

3. Build the firmware with ImageAvatar selected.

Use menuconfig:

```text
StackChan Avatar -> Avatar Skin -> Image Avatar
```

Then:

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
idf.py fullclean
idf.py build
```

4. Flash and smoke-test on hardware.

Minimum acceptance:

- boots without crash;
- Avatar app opens;
- neutral face displays correctly;
- blink modifier changes eye frames;
- speech/speaking changes mouth frames;
- app/WebSocket/BLE avatar control still changes emotion;
- close/reopen path does not leak or leave hidden LVGL objects;
- OTA/server/app features are not broken by the skin switch.

5. Feed device findings back into this repo.

Update:

- `docs/stackchan-official-device-context.md`;
- `docs/stackchan-image-pack-generation-skill.md`;
- `docs/superpowers/plans/2026-06-30-stackchan-image-avatar.md`;
- `skills/stackchan-image-pack/SKILL.md` if asset dimensions, frame counts, or conversion rules change.

## Documentation Maintenance Rule

Keep StackChan documentation in the root workspace current whenever any of these change:

- official firmware source pin or upstream branch;
- local fork/submodule branch strategy;
- image-pack frame counts, dimensions, anchors, or asset conversion path;
- ESP-IDF build, flash, or test commands;
- findings from real StackChan device smoke tests;
- MCP/server/app integration assumptions.

The root docs explain the why and workflow; the `projects/StackChan` submodule contains the implementation. Do not bury durable process knowledge only inside ad hoc terminal history or submodule commits.

## Upstream Sync Discipline

Treat `projects/StackChan` as a small, reviewable fork of official M5Stack source, not as a permanent hard fork.

Required rules for future changes:

- Keep `m5stack/StackChan` configured as read-only `upstream` and regularly fetch it before larger work.
- Prefer additive code under isolated directories such as `firmware/main/stackchan/avatar/skins/image/`.
- Keep official core abstractions stable unless a compile error or narrow integration seam requires a small change.
- Avoid broad rewrites of `Avatar`, `Feature`, JSON protocol, HAL, app/server protocol, or factory firmware flows.
- Put host-testable logic in standalone files before touching LVGL or ESP-IDF runtime code.
- Keep commits small and topic-focused so future `upstream/main` merges are easy to inspect.
- When a change touches an official file, explain why that file had to change in the commit message or nearby root documentation.
- Do not vendor generated firmware dependencies into the root workspace; keep dependency output ignored inside the StackChan submodule.
- After each meaningful submodule commit, update the root submodule pointer and any affected StackChan docs together.

Before merging official updates:

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan
git fetch upstream
git checkout codex/image-avatar
git rebase upstream/main
cmake --build firmware/build-host-tests
ctest --test-dir firmware/build-host-tests --output-on-failure
```

If a rebase conflict appears in a large official file, stop and reassess the local patch shape before resolving mechanically. The preferred fix is usually to shrink or move our local change behind a smaller seam, not to keep expanding the conflict surface.

## Current Decision

The next engineering step is not more image generation. The next step is ESP-IDF and device bring-up:

```text
source/install ESP-IDF -> default build -> image-skin build -> flash -> device smoke test
```

Only generate more frames or new art after device screenshots show a specific problem.
