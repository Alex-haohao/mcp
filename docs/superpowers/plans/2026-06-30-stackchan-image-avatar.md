# StackChan ImageAvatar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a custom image-based StackChan avatar skin to the official ESP-IDF firmware while preserving the official AI Agent, mobile app control, OTA, WebSocket/BLE avatar protocol, motion, speech, decorators, and default avatar.

**Required context:** Read `docs/stackchan-official-device-context.md` before executing this plan. It records the current official M5Stack product documentation, fork-backed `projects/StackChan` submodule, official firmware source entry points, assets partition behavior, current generated pack status, and the Arduino-vs-ESP-IDF boundary.

**Architecture:** Add a new `ImageAvatar` skin beside `DefaultAvatar`; do not replace or delete the official skin. Keep the semantic control layer unchanged (`Emotion`, `leftEye`, `rightEye`, `mouth`, modifiers, decorators) and map those values into image/sprite frame selection. Put all pure mapping logic in host-testable files before integrating LVGL.

**Tech Stack:** Official `m5stack/StackChan` firmware, ESP-IDF v5.5.4, C++17, LVGL, `smooth_lvgl`, official host-side CMake tests under `firmware/tests`.

**Upstream policy:** Keep this fork easy to sync with official `m5stack/StackChan`. Prefer additive files under `firmware/main/stackchan/avatar/skins/image/`, keep official core abstractions and protocols unchanged, and make every official-file edit narrow enough to survive future `upstream/main` rebases.

**Current execution status (2026-06-30):** Tasks 1 and 2 are complete. Tasks 3, 4, 5, 6, 8, and 9 were implemented in one complete pass rather than the older staged 3-expression path: the current submodule commit is `834b27f feat: add image avatar skin`, pushed to `origin/codex/image-avatar`. The implementation includes all six emotions, four eye frames per side, four mouth frames, Kconfig selection, firmware-local docs, and complete generated LVGL descriptors. Host tests pass, `git diff --check` passes, and a temporary fake-LVGL syntax/preprocessor check confirms all 73 generated assets are referenced. Full `idf.py build`, flash, and hardware smoke tests remain pending because `idf.py` is not installed or sourced in this environment.

---

## Scope Boundary

The implementation target is the fork-backed StackChan submodule in this MCP workspace. The submodule tracks `https://github.com/Alex-haohao/StackChan.git` as `origin` and should keep `https://github.com/m5stack/StackChan.git` as read-only `upstream`.

Use this local checkout path when executing:

```bash
/Users/tianhaoxi/project/mcp/projects/StackChan
```

Branch name:

```bash
codex/image-avatar
```

Do not use an Arduino sketch as the production implementation. Arduino and `StackChan-BSP` are acceptable only for asset display bring-up.

Do not modify the official App/Server protocol in the first implementation. The first version must work through the existing avatar JSON shape and official `SetEmotion()` path.

## What You Need To Prepare

### Hardware And Firmware Tools

- StackChan device with battery charged or stable USB-C power.
- USB-C data cable.
- Working ESP-IDF v5.5.4 environment.
- Ability to flash and monitor the device with `idf.py flash monitor`.
- The official StackChan mobile app available for remote avatar/dance smoke testing.

Toolchain checks:

```bash
idf.py --version
python3 --version
cmake --version
git --version
```

Expected:

```text
ESP-IDF v5.5.4 or compatible 5.5.x
Python 3.x
CMake 3.16 or newer
Git available
```

### Image Asset Contract

Prepare transparent PNG source assets at final device scale. The display is 320x240, so avoid oversized source assets that will only be downsampled.

Minimum first pack:

```text
avatar-packs/my-stackchan/source/
  body/base.png
  neutral/left_eye_0.png
  neutral/left_eye_1.png
  neutral/left_eye_2.png
  neutral/left_eye_3.png
  neutral/right_eye_0.png
  neutral/right_eye_1.png
  neutral/right_eye_2.png
  neutral/right_eye_3.png
  neutral/mouth_0.png
  neutral/mouth_1.png
  neutral/mouth_2.png
  neutral/mouth_3.png
```

Recommended full pack:

```text
neutral
happy
angry
sad
doubt
sleepy
```

Each emotion directory should have:

```text
left_eye_0..3.png    # Open to closed or calm to expressive frames.
right_eye_0..3.png
mouth_0..3.png       # Closed to open mouth frames for speech.
```

Asset rules:

- Keep each part tightly cropped with transparent background.
- Use consistent anchor points across emotions.
- Use the same frame count for left and right eye in one pack.
- Use the image-pack skill default of 4 eye frames and 4 mouth frames for the first pack. The renderer mapping must read `frameCount` from the pack metadata so later packs can deliberately expand to 6 mouth frames or 6-7 eye frames after firmware smoke testing.
- Do not use high-count full-screen animation frames for the official ImageAvatar path. A 320x240 RGB565 full frame is 153,600 bytes before descriptors, so full-screen animation quickly consumes Flash/PSRAM budget.
- Use original, licensed, or self-generated art only.

## File Structure

Create these files in the official StackChan checkout:

```text
firmware/main/stackchan/avatar/skins/image/image_avatar_mapping.h
firmware/main/stackchan/avatar/skins/image/image_avatar_mapping.cpp
firmware/main/stackchan/avatar/skins/image/image_avatar_pack.h
firmware/main/stackchan/avatar/skins/image/image_sprite_feature.h
firmware/main/stackchan/avatar/skins/image/image_sprite_feature.cpp
firmware/main/stackchan/avatar/skins/image/image_avatar.h
firmware/main/stackchan/avatar/skins/image/image_avatar.cpp
firmware/main/stackchan/avatar/skins/image/packs/my_stackchan_pack.h
firmware/main/stackchan/avatar/skins/image/packs/my_stackchan_pack.cpp
firmware/main/stackchan/avatar/skins/image/packs/assets/my_stackchan_*.c
firmware/tests/image_avatar_mapping_test.cpp
```

Modify these existing files:

```text
firmware/tests/CMakeLists.txt
firmware/main/Kconfig.projbuild
firmware/main/apps/app_avatar/app_avatar.cpp
```

Do not modify these files in the first version unless a compile error proves a narrow change is required:

```text
firmware/main/stackchan/avatar/avatar/avatar.h
firmware/main/stackchan/avatar/avatar/elements/feature.h
firmware/main/stackchan/json/json_helper.cpp
firmware/main/hal/board/stackchan_display.cc
firmware/main/stackchan/avatar/skins/default/default.h
firmware/main/stackchan/avatar/skins/default/default.cpp
```

## Task 1: Prepare Official Firmware Submodule

**Files:**
- No source files changed.

- [ ] **Step 1: Verify the submodule checkout and remotes**

```bash
cd /Users/tianhaoxi/project/mcp
git submodule update --init projects/StackChan
git -C projects/StackChan remote get-url upstream >/dev/null 2>&1 || \
  git -C projects/StackChan remote add upstream https://github.com/m5stack/StackChan.git
git -C projects/StackChan remote set-url --push upstream DISABLED
git -C projects/StackChan remote -v
git -C projects/StackChan status --short
```

Expected: `origin` points to `Alex-haohao/StackChan`; `upstream` points to `m5stack/StackChan` with push disabled; `git status --short` is empty.

- [ ] **Step 2: Checkout the feature branch**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan
git fetch origin
git checkout codex/image-avatar
```

Expected: branch is `codex/image-avatar` tracking `origin/codex/image-avatar`.

- [ ] **Step 3: Fetch firmware dependencies**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
python3 ./fetch_repos.py
```

Expected: dependencies are fetched under `firmware/`; skipped patches are acceptable only if the script explicitly says the patch cannot apply cleanly to an already-compatible dependency.

- [ ] **Step 4: Run existing host tests**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
cmake -S tests -B build-host-tests
cmake --build build-host-tests
ctest --test-dir build-host-tests --output-on-failure
```

Expected: existing `motion_math_test` passes before new work starts.

## Task 2: Add Pure ImageAvatar Mapping Logic

**Files:**
- Create: `firmware/main/stackchan/avatar/skins/image/image_avatar_mapping.h`
- Create: `firmware/main/stackchan/avatar/skins/image/image_avatar_mapping.cpp`
- Create: `firmware/tests/image_avatar_mapping_test.cpp`
- Modify: `firmware/tests/CMakeLists.txt`

- [ ] **Step 1: Write the failing host test**

Create `firmware/tests/image_avatar_mapping_test.cpp`:

```cpp
#include <cstdlib>
#include <iostream>
#include <stackchan/avatar/avatar/elements/emotion.h>
#include <stackchan/avatar/skins/image/image_avatar_mapping.h>

namespace {

using stackchan::avatar::Emotion;
using stackchan::avatar::image::emotionAssetName;
using stackchan::avatar::image::mapNormalizedToRange;
using stackchan::avatar::image::selectFrameForWeight;

void expectEqual(int actual, int expected, const char* label)
{
    if (actual != expected) {
        std::cerr << label << ": expected " << expected << ", got " << actual << '\n';
        std::exit(1);
    }
}

void expectString(const char* actual, const char* expected, const char* label)
{
    if (std::string(actual) != expected) {
        std::cerr << label << ": expected " << expected << ", got " << actual << '\n';
        std::exit(1);
    }
}

void testFrameSelection()
{
    expectEqual(selectFrameForWeight(-20, 3), 0, "negative weight clamps to first frame");
    expectEqual(selectFrameForWeight(0, 3), 0, "zero weight uses first frame");
    expectEqual(selectFrameForWeight(50, 3), 1, "middle weight uses middle frame");
    expectEqual(selectFrameForWeight(100, 3), 2, "full weight uses last frame");
    expectEqual(selectFrameForWeight(180, 3), 2, "high weight clamps to last frame");
    expectEqual(selectFrameForWeight(80, 1), 0, "one-frame sprite always selects zero");
}

void testNormalizedRangeMapping()
{
    expectEqual(mapNormalizedToRange(-100, -16, 16), -16, "min normalized maps to min");
    expectEqual(mapNormalizedToRange(0, -16, 16), 0, "center normalized maps to center");
    expectEqual(mapNormalizedToRange(100, -16, 16), 16, "max normalized maps to max");
    expectEqual(mapNormalizedToRange(150, -16, 16), 16, "high normalized clamps");
    expectEqual(mapNormalizedToRange(-150, -16, 16), -16, "low normalized clamps");
}

void testEmotionNames()
{
    expectString(emotionAssetName(Emotion::Neutral), "neutral", "neutral emotion");
    expectString(emotionAssetName(Emotion::Happy), "happy", "happy emotion");
    expectString(emotionAssetName(Emotion::Angry), "angry", "angry emotion");
    expectString(emotionAssetName(Emotion::Sad), "sad", "sad emotion");
    expectString(emotionAssetName(Emotion::Doubt), "doubt", "doubt emotion");
    expectString(emotionAssetName(Emotion::Sleepy), "sleepy", "sleepy emotion");
}

}  // namespace

int main()
{
    testFrameSelection();
    testNormalizedRangeMapping();
    testEmotionNames();
    return 0;
}
```

- [ ] **Step 2: Add the test target**

Modify `firmware/tests/CMakeLists.txt` by adding:

```cmake
add_executable(image_avatar_mapping_test
    image_avatar_mapping_test.cpp
    ../main/stackchan/avatar/skins/image/image_avatar_mapping.cpp
)

target_include_directories(image_avatar_mapping_test PRIVATE
    ../main
)

target_compile_features(image_avatar_mapping_test PRIVATE cxx_std_17)

add_test(NAME image_avatar_mapping_test COMMAND $<TARGET_FILE:image_avatar_mapping_test>)
```

- [ ] **Step 3: Run the test and verify it fails before implementation**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
cmake -S tests -B build-host-tests
cmake --build build-host-tests
```

Expected: build fails because `image_avatar_mapping.h` does not exist.

- [ ] **Step 4: Add the mapping header**

Create `firmware/main/stackchan/avatar/skins/image/image_avatar_mapping.h`:

```cpp
#pragma once

#include <stackchan/avatar/avatar/elements/emotion.h>

namespace stackchan::avatar::image {

int clampInt(int value, int minValue, int maxValue);
int selectFrameForWeight(int weight, int frameCount);
int mapNormalizedToRange(int normalized, int minValue, int maxValue);
const char* emotionAssetName(Emotion emotion);

}  // namespace stackchan::avatar::image
```

- [ ] **Step 5: Add the mapping implementation**

Create `firmware/main/stackchan/avatar/skins/image/image_avatar_mapping.cpp`:

```cpp
#include "image_avatar_mapping.h"

namespace stackchan::avatar::image {

int clampInt(int value, int minValue, int maxValue)
{
    if (value < minValue) {
        return minValue;
    }
    if (value > maxValue) {
        return maxValue;
    }
    return value;
}

int selectFrameForWeight(int weight, int frameCount)
{
    if (frameCount <= 1) {
        return 0;
    }

    const int clampedWeight = clampInt(weight, 0, 100);
    const int maxFrame      = frameCount - 1;
    return (clampedWeight * maxFrame + 50) / 100;
}

int mapNormalizedToRange(int normalized, int minValue, int maxValue)
{
    const int clamped = clampInt(normalized, -100, 100);
    return minValue + ((clamped + 100) * (maxValue - minValue) + 100) / 200;
}

const char* emotionAssetName(Emotion emotion)
{
    switch (emotion) {
        case Emotion::Happy:
            return "happy";
        case Emotion::Angry:
            return "angry";
        case Emotion::Sad:
            return "sad";
        case Emotion::Doubt:
            return "doubt";
        case Emotion::Sleepy:
            return "sleepy";
        case Emotion::Neutral:
        default:
            return "neutral";
    }
}

}  // namespace stackchan::avatar::image
```

- [ ] **Step 6: Run host tests**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
cmake -S tests -B build-host-tests
cmake --build build-host-tests
ctest --test-dir build-host-tests --output-on-failure
```

Expected: `motion_math_test` and `image_avatar_mapping_test` pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan
git add firmware/main/stackchan/avatar/skins/image/image_avatar_mapping.h \
        firmware/main/stackchan/avatar/skins/image/image_avatar_mapping.cpp \
        firmware/tests/image_avatar_mapping_test.cpp \
        firmware/tests/CMakeLists.txt
git commit -m "test: add image avatar mapping coverage"
```

## Task 3: Define The Image Avatar Pack Model

**Files:**
- Create: `firmware/main/stackchan/avatar/skins/image/image_avatar_pack.h`
- Create: `firmware/main/stackchan/avatar/skins/image/packs/my_stackchan_pack.h`
- Create: `firmware/main/stackchan/avatar/skins/image/packs/my_stackchan_pack.cpp`
- Create: `firmware/main/stackchan/avatar/skins/image/packs/assets/my_stackchan_*.c`

- [ ] **Step 1: Convert source PNGs into LVGL image descriptors**

Use the same LVGL C image descriptor style already used by official decorators. Generate one `.c` file per image and use stable symbol names:

```text
my_stackchan_neutral_head
my_stackchan_neutral_left_eye_0
my_stackchan_neutral_left_eye_1
my_stackchan_neutral_left_eye_2
my_stackchan_neutral_right_eye_0
my_stackchan_neutral_right_eye_1
my_stackchan_neutral_right_eye_2
my_stackchan_neutral_mouth_0
my_stackchan_neutral_mouth_1
my_stackchan_neutral_mouth_2
```

Repeat the same pattern for `happy` and `sad` in the first pack.

Expected: generated files live under:

```text
firmware/main/stackchan/avatar/skins/image/packs/assets/
```

- [ ] **Step 2: Add the pack descriptor header**

Create `firmware/main/stackchan/avatar/skins/image/image_avatar_pack.h`:

```cpp
#pragma once

#include <array>
#include <cstddef>
#include <lvgl.h>
#include <stackchan/avatar/avatar/elements/emotion.h>

namespace stackchan::avatar::image {

struct ImageSpriteSet {
    const lv_image_dsc_t* const* frames;
    int frameCount;
    int centerX;
    int centerY;
    int minOffsetX;
    int maxOffsetX;
    int minOffsetY;
    int maxOffsetY;
};

struct ImageExpressionSet {
    Emotion emotion;
    const lv_image_dsc_t* head;
    ImageSpriteSet leftEye;
    ImageSpriteSet rightEye;
    ImageSpriteSet mouth;
};

struct ImageAvatarPack {
    const char* id;
    const ImageExpressionSet* expressions;
    int expressionCount;
};

const ImageExpressionSet& expressionForEmotion(const ImageAvatarPack& pack, Emotion emotion);

}  // namespace stackchan::avatar::image
```

- [ ] **Step 3: Add pack lookup implementation to the same header owner**

Create `firmware/main/stackchan/avatar/skins/image/image_avatar_pack.cpp`:

```cpp
#include "image_avatar_pack.h"

namespace stackchan::avatar::image {

const ImageExpressionSet& expressionForEmotion(const ImageAvatarPack& pack, Emotion emotion)
{
    for (int i = 0; i < pack.expressionCount; ++i) {
        if (pack.expressions[i].emotion == emotion) {
            return pack.expressions[i];
        }
    }
    for (int i = 0; i < pack.expressionCount; ++i) {
        if (pack.expressions[i].emotion == Emotion::Neutral) {
            return pack.expressions[i];
        }
    }
    return pack.expressions[0];
}

}  // namespace stackchan::avatar::image
```

- [ ] **Step 4: Add concrete pack declarations**

Create `firmware/main/stackchan/avatar/skins/image/packs/my_stackchan_pack.h`:

```cpp
#pragma once

#include <stackchan/avatar/skins/image/image_avatar_pack.h>

namespace stackchan::avatar::image::packs {

extern const ImageAvatarPack kMyStackChanPack;

}  // namespace stackchan::avatar::image::packs
```

- [ ] **Step 5: Add concrete pack definitions**

Create `firmware/main/stackchan/avatar/skins/image/packs/my_stackchan_pack.cpp` using the generated asset names. The first version must include at least `neutral`, `happy`, and `sad`.

```cpp
#include "my_stackchan_pack.h"

LV_IMAGE_DECLARE(my_stackchan_neutral_head);
LV_IMAGE_DECLARE(my_stackchan_neutral_left_eye_0);
LV_IMAGE_DECLARE(my_stackchan_neutral_left_eye_1);
LV_IMAGE_DECLARE(my_stackchan_neutral_left_eye_2);
LV_IMAGE_DECLARE(my_stackchan_neutral_right_eye_0);
LV_IMAGE_DECLARE(my_stackchan_neutral_right_eye_1);
LV_IMAGE_DECLARE(my_stackchan_neutral_right_eye_2);
LV_IMAGE_DECLARE(my_stackchan_neutral_mouth_0);
LV_IMAGE_DECLARE(my_stackchan_neutral_mouth_1);
LV_IMAGE_DECLARE(my_stackchan_neutral_mouth_2);

LV_IMAGE_DECLARE(my_stackchan_happy_head);
LV_IMAGE_DECLARE(my_stackchan_happy_left_eye_0);
LV_IMAGE_DECLARE(my_stackchan_happy_left_eye_1);
LV_IMAGE_DECLARE(my_stackchan_happy_left_eye_2);
LV_IMAGE_DECLARE(my_stackchan_happy_right_eye_0);
LV_IMAGE_DECLARE(my_stackchan_happy_right_eye_1);
LV_IMAGE_DECLARE(my_stackchan_happy_right_eye_2);
LV_IMAGE_DECLARE(my_stackchan_happy_mouth_0);
LV_IMAGE_DECLARE(my_stackchan_happy_mouth_1);
LV_IMAGE_DECLARE(my_stackchan_happy_mouth_2);

LV_IMAGE_DECLARE(my_stackchan_sad_head);
LV_IMAGE_DECLARE(my_stackchan_sad_left_eye_0);
LV_IMAGE_DECLARE(my_stackchan_sad_left_eye_1);
LV_IMAGE_DECLARE(my_stackchan_sad_left_eye_2);
LV_IMAGE_DECLARE(my_stackchan_sad_right_eye_0);
LV_IMAGE_DECLARE(my_stackchan_sad_right_eye_1);
LV_IMAGE_DECLARE(my_stackchan_sad_right_eye_2);
LV_IMAGE_DECLARE(my_stackchan_sad_mouth_0);
LV_IMAGE_DECLARE(my_stackchan_sad_mouth_1);
LV_IMAGE_DECLARE(my_stackchan_sad_mouth_2);

namespace stackchan::avatar::image::packs {
namespace {

const lv_image_dsc_t* kNeutralLeftEyes[] = {
    &my_stackchan_neutral_left_eye_0,
    &my_stackchan_neutral_left_eye_1,
    &my_stackchan_neutral_left_eye_2,
};
const lv_image_dsc_t* kNeutralRightEyes[] = {
    &my_stackchan_neutral_right_eye_0,
    &my_stackchan_neutral_right_eye_1,
    &my_stackchan_neutral_right_eye_2,
};
const lv_image_dsc_t* kNeutralMouths[] = {
    &my_stackchan_neutral_mouth_0,
    &my_stackchan_neutral_mouth_1,
    &my_stackchan_neutral_mouth_2,
};

const lv_image_dsc_t* kHappyLeftEyes[] = {
    &my_stackchan_happy_left_eye_0,
    &my_stackchan_happy_left_eye_1,
    &my_stackchan_happy_left_eye_2,
};
const lv_image_dsc_t* kHappyRightEyes[] = {
    &my_stackchan_happy_right_eye_0,
    &my_stackchan_happy_right_eye_1,
    &my_stackchan_happy_right_eye_2,
};
const lv_image_dsc_t* kHappyMouths[] = {
    &my_stackchan_happy_mouth_0,
    &my_stackchan_happy_mouth_1,
    &my_stackchan_happy_mouth_2,
};

const lv_image_dsc_t* kSadLeftEyes[] = {
    &my_stackchan_sad_left_eye_0,
    &my_stackchan_sad_left_eye_1,
    &my_stackchan_sad_left_eye_2,
};
const lv_image_dsc_t* kSadRightEyes[] = {
    &my_stackchan_sad_right_eye_0,
    &my_stackchan_sad_right_eye_1,
    &my_stackchan_sad_right_eye_2,
};
const lv_image_dsc_t* kSadMouths[] = {
    &my_stackchan_sad_mouth_0,
    &my_stackchan_sad_mouth_1,
    &my_stackchan_sad_mouth_2,
};

ImageSpriteSet makeEyeSet(const lv_image_dsc_t* const* frames)
{
    return ImageSpriteSet{frames, 3, 0, -16, -16, 16, -16, 16};
}

ImageSpriteSet makeMouthSet(const lv_image_dsc_t* const* frames)
{
    return ImageSpriteSet{frames, 3, 0, 26, -12, 12, -8, 8};
}

const ImageExpressionSet kExpressions[] = {
    {Emotion::Neutral, &my_stackchan_neutral_head, makeEyeSet(kNeutralLeftEyes), makeEyeSet(kNeutralRightEyes), makeMouthSet(kNeutralMouths)},
    {Emotion::Happy, &my_stackchan_happy_head, makeEyeSet(kHappyLeftEyes), makeEyeSet(kHappyRightEyes), makeMouthSet(kHappyMouths)},
    {Emotion::Sad, &my_stackchan_sad_head, makeEyeSet(kSadLeftEyes), makeEyeSet(kSadRightEyes), makeMouthSet(kSadMouths)},
};

}  // namespace

const ImageAvatarPack kMyStackChanPack = {
    "my-stackchan",
    kExpressions,
    static_cast<int>(sizeof(kExpressions) / sizeof(kExpressions[0])),
};

}  // namespace stackchan::avatar::image::packs
```

- [ ] **Step 6: Build firmware to catch generated asset symbol errors**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
idf.py build
```

Expected: build may fail if image conversion produced different symbol names. Rename generated symbols or declarations until the names match exactly.

- [ ] **Step 7: Commit**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan
git add firmware/main/stackchan/avatar/skins/image/image_avatar_pack.h \
        firmware/main/stackchan/avatar/skins/image/image_avatar_pack.cpp \
        firmware/main/stackchan/avatar/skins/image/packs
git commit -m "feat: add image avatar pack descriptors"
```

## Task 4: Add The LVGL ImageSpriteFeature

**Files:**
- Create: `firmware/main/stackchan/avatar/skins/image/image_sprite_feature.h`
- Create: `firmware/main/stackchan/avatar/skins/image/image_sprite_feature.cpp`

- [ ] **Step 1: Add the feature header**

Create `firmware/main/stackchan/avatar/skins/image/image_sprite_feature.h`:

```cpp
#pragma once

#include "image_avatar_pack.h"
#include <memory>
#include <smooth_lvgl.hpp>
#include <stackchan/avatar/avatar/elements/feature.h>

namespace stackchan::avatar::image {

class ImageSpriteFeature : public Feature {
public:
    ImageSpriteFeature(lv_obj_t* parent, const ImageSpriteSet& spriteSet);
    ~ImageSpriteFeature() override;

    void setSpriteSet(const ImageSpriteSet& spriteSet);
    void setPosition(const uitk::Vector2i& position) override;
    void setWeight(int weight) override;
    void setRotation(int rotation) override;
    void setVisible(bool visible) override;
    void setSize(int size) override;

private:
    void refreshFrame();
    void refreshPosition();

    const ImageSpriteSet* _sprite_set = nullptr;
    std::unique_ptr<uitk::lvgl_cpp::Image> _image;
};

}  // namespace stackchan::avatar::image
```

- [ ] **Step 2: Add the feature implementation**

Create `firmware/main/stackchan/avatar/skins/image/image_sprite_feature.cpp`:

```cpp
#include "image_sprite_feature.h"
#include "image_avatar_mapping.h"

using namespace uitk;
using namespace uitk::lvgl_cpp;

namespace stackchan::avatar::image {

ImageSpriteFeature::ImageSpriteFeature(lv_obj_t* parent, const ImageSpriteSet& spriteSet)
{
    _image = std::make_unique<Image>(parent);
    _image->setAlign(LV_ALIGN_CENTER);
    setSpriteSet(spriteSet);
    setPosition(_position);
    setWeight(0);
    setRotation(0);
    setVisible(true);
}

ImageSpriteFeature::~ImageSpriteFeature() = default;

void ImageSpriteFeature::setSpriteSet(const ImageSpriteSet& spriteSet)
{
    _sprite_set = &spriteSet;
    refreshFrame();
    refreshPosition();
}

void ImageSpriteFeature::setPosition(const Vector2i& position)
{
    Element::setPosition(position);
    refreshPosition();
}

void ImageSpriteFeature::setWeight(int weight)
{
    Feature::setWeight(weight);
    refreshFrame();
}

void ImageSpriteFeature::setRotation(int rotation)
{
    Element::setRotation(rotation);
    if (_image) {
        _image->setTransformPivot(_image->getWidth() / 2, _image->getHeight() / 2);
        _image->setRotation(_rotation);
    }
}

void ImageSpriteFeature::setVisible(bool visible)
{
    Element::setVisible(visible);
    if (_image) {
        _image->setHidden(!visible);
    }
}

void ImageSpriteFeature::setSize(int size)
{
    Feature::setSize(size);
}

void ImageSpriteFeature::refreshFrame()
{
    if (!_image || !_sprite_set || !_sprite_set->frames || _sprite_set->frameCount <= 0) {
        return;
    }

    const int frame = selectFrameForWeight(_weight, _sprite_set->frameCount);
    _image->setSrc(_sprite_set->frames[frame]);
}

void ImageSpriteFeature::refreshPosition()
{
    if (!_image || !_sprite_set) {
        return;
    }

    const int x = _sprite_set->centerX + mapNormalizedToRange(_position.x, _sprite_set->minOffsetX, _sprite_set->maxOffsetX);
    const int y = _sprite_set->centerY + mapNormalizedToRange(_position.y, _sprite_set->minOffsetY, _sprite_set->maxOffsetY);
    _image->setPos(x, y);
}

}  // namespace stackchan::avatar::image
```

- [ ] **Step 3: Build**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
idf.py build
```

Expected: build succeeds or fails only on exact wrapper method names. If a `smooth_lvgl` method name differs, adjust only the method call and keep the class contract unchanged.

- [ ] **Step 4: Commit**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan
git add firmware/main/stackchan/avatar/skins/image/image_sprite_feature.h \
        firmware/main/stackchan/avatar/skins/image/image_sprite_feature.cpp
git commit -m "feat: add image sprite avatar feature"
```

## Task 5: Add ImageAvatar Skin

**Files:**
- Create: `firmware/main/stackchan/avatar/skins/image/image_avatar.h`
- Create: `firmware/main/stackchan/avatar/skins/image/image_avatar.cpp`

- [ ] **Step 1: Add the avatar header**

Create `firmware/main/stackchan/avatar/skins/image/image_avatar.h`:

```cpp
#pragma once

#include "image_avatar_pack.h"
#include <memory>
#include <smooth_lvgl.hpp>
#include <stackchan/avatar/avatar/avatar.h>
#include <stackchan/avatar/skins/default/default.h>

namespace stackchan::avatar::image {

class ImageAvatar : public Avatar {
public:
    explicit ImageAvatar(const ImageAvatarPack& pack);

    void init(lv_obj_t* parent, const lv_font_t* font = &lv_font_montserrat_16);
    void setEmotion(const Emotion& emotion) override;
    uitk::lvgl_cpp::Container* getPanel() const;

private:
    void applyExpression(const ImageExpressionSet& expression);

    const ImageAvatarPack& _pack;
    const ImageExpressionSet* _current_expression = nullptr;
    std::unique_ptr<uitk::lvgl_cpp::Container> _panel;
    std::unique_ptr<uitk::lvgl_cpp::Image> _head;
};

}  // namespace stackchan::avatar::image
```

- [ ] **Step 2: Add the avatar implementation**

Create `firmware/main/stackchan/avatar/skins/image/image_avatar.cpp`:

```cpp
#include "image_avatar.h"
#include "image_sprite_feature.h"

using namespace uitk::lvgl_cpp;

namespace stackchan::avatar::image {

ImageAvatar::ImageAvatar(const ImageAvatarPack& pack) : _pack(pack)
{
}

void ImageAvatar::init(lv_obj_t* parent, const lv_font_t* font)
{
    _panel = std::make_unique<Container>(parent);
    _panel->align(LV_ALIGN_CENTER, 0, 0);
    _panel->setSize(320, 240);
    _panel->setRadius(0);
    _panel->setBorderWidth(0);
    _panel->setBgColor(lv_color_black());
    _panel->removeFlag(LV_OBJ_FLAG_SCROLLABLE);

    const auto& expression = expressionForEmotion(_pack, Emotion::Neutral);
    _current_expression    = &expression;

    _head = std::make_unique<Image>(_panel->get());
    _head->setAlign(LV_ALIGN_CENTER);
    _head->setSrc(expression.head);

    _key_elements.leftEye  = std::make_unique<ImageSpriteFeature>(_panel->get(), expression.leftEye);
    _key_elements.rightEye = std::make_unique<ImageSpriteFeature>(_panel->get(), expression.rightEye);
    _key_elements.mouth    = std::make_unique<ImageSpriteFeature>(_panel->get(), expression.mouth);

    _key_elements.speechBubble =
        std::make_unique<DefaultSpeechBubble>(_panel->get(), lv_color_white(), lv_color_black(), font);
}

void ImageAvatar::setEmotion(const Emotion& emotion)
{
    Avatar::setEmotion(emotion);
    applyExpression(expressionForEmotion(_pack, emotion));
}

Container* ImageAvatar::getPanel() const
{
    return _panel.get();
}

void ImageAvatar::applyExpression(const ImageExpressionSet& expression)
{
    _current_expression = &expression;

    if (_head) {
        _head->setSrc(expression.head);
    }

    auto* leftEye = dynamic_cast<ImageSpriteFeature*>(_key_elements.leftEye.get());
    if (leftEye) {
        leftEye->setSpriteSet(expression.leftEye);
    }

    auto* rightEye = dynamic_cast<ImageSpriteFeature*>(_key_elements.rightEye.get());
    if (rightEye) {
        rightEye->setSpriteSet(expression.rightEye);
    }

    auto* mouth = dynamic_cast<ImageSpriteFeature*>(_key_elements.mouth.get());
    if (mouth) {
        mouth->setSpriteSet(expression.mouth);
    }
}

}  // namespace stackchan::avatar::image
```

- [ ] **Step 3: Build**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
idf.py build
```

Expected: build succeeds. If `DefaultSpeechBubble` coupling becomes a compile problem, extract it into `firmware/main/stackchan/avatar/skins/common/lvgl_speech_bubble.*` and update both default and image skins in the same commit.

- [ ] **Step 4: Commit**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan
git add firmware/main/stackchan/avatar/skins/image/image_avatar.h \
        firmware/main/stackchan/avatar/skins/image/image_avatar.cpp
git commit -m "feat: add image avatar skin"
```

## Task 6: Wire ImageAvatar Behind A Firmware Config

**Files:**
- Modify: `firmware/main/Kconfig.projbuild`
- Modify: `firmware/main/apps/app_avatar/app_avatar.cpp`

- [ ] **Step 1: Add config flag**

Modify `firmware/main/Kconfig.projbuild`:

```text
choice STACKCHAN_AVATAR_SKIN
    prompt "Avatar Skin"
    default STACKCHAN_AVATAR_SKIN_DEFAULT

    config STACKCHAN_AVATAR_SKIN_DEFAULT
        bool "Default Avatar"

    config STACKCHAN_AVATAR_SKIN_IMAGE
        bool "Image Avatar"
endchoice
```

- [ ] **Step 2: Add includes**

Modify `firmware/main/apps/app_avatar/app_avatar.cpp`:

```cpp
#include <stackchan/avatar/skins/image/image_avatar.h>
```

- [ ] **Step 3: Replace only the avatar construction block**

Replace:

```cpp
auto avatar = std::make_unique<avatar::DefaultAvatar>();
avatar->init(lv_screen_active());
avatar->getPanel()->onClick().connect([&]() { _screen_clicked_flag = true; });
GetStackChan().attachAvatar(std::move(avatar));
```

With:

```cpp
#if CONFIG_STACKCHAN_AVATAR_SKIN_IMAGE
    auto avatar = std::make_unique<avatar::image::ImageAvatar>();
#else
    auto avatar = std::make_unique<avatar::DefaultAvatar>();
#endif
    avatar->init(lv_screen_active());
    avatar->getPanel()->onClick().connect([&]() { _screen_clicked_flag = true; });
    GetStackChan().attachAvatar(std::move(avatar));
```

- [ ] **Step 4: Build with default avatar**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
idf.py build
```

Expected: build succeeds with `CONFIG_STACKCHAN_AVATAR_SKIN_DEFAULT` selected.

- [ ] **Step 5: Build with ImageAvatar enabled**

Use menuconfig:

```text
StackChan Avatar -> Avatar Skin -> Image Avatar
```

Then build:

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
idf.py fullclean
idf.py build
```

Expected: build succeeds with the image skin enabled.

- [ ] **Step 6: Commit**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan
git add firmware/main/Kconfig.projbuild firmware/main/apps/app_avatar/app_avatar.cpp
git commit -m "feat: wire image avatar behind config"
```

## Task 7: Verify Official Behavior Is Preserved

**Files:**
- No source files changed unless verification exposes a specific defect.

- [ ] **Step 1: Run host tests**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
cmake -S tests -B build-host-tests
cmake --build build-host-tests
ctest --test-dir build-host-tests --output-on-failure
```

Expected: all host tests pass.

- [ ] **Step 2: Run firmware build**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
idf.py build
```

Expected: build succeeds.

- [ ] **Step 3: Flash and monitor**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
idf.py flash monitor
```

Expected:

```text
Device boots.
Avatar app opens.
ImageAvatar appears when `CONFIG_STACKCHAN_AVATAR_SKIN_IMAGE` is selected.
DefaultAvatar still appears when `CONFIG_STACKCHAN_AVATAR_SKIN_DEFAULT` is selected.
No reboot loop.
No LVGL assertion.
No image allocation failure.
```

- [ ] **Step 4: Manual feature smoke**

Check these behaviors on device:

```text
AI Agent can start.
Assistant messages still appear in speech bubble.
Speaking still drives mouth open/close.
Official app can send avatar control.
Official app can send dance control.
Happy/sad/sleepy emotion changes update the image set.
Touch/head pet still triggers happy/decorator behavior.
Call overlay still hides and restores eyes/mouth.
OTA and app center screens still open.
```

- [ ] **Step 5: Capture verification evidence**

Record these artifacts outside the firmware source tree:

```text
build log summary
flash log summary
photo or short video of neutral expression
photo or short video of happy expression
photo or short video of speech mouth movement
photo or short video of app remote avatar control
```

## Task 8: Polish Asset Pack And Add Full Expressions

**Files:**
- Modify: `firmware/main/stackchan/avatar/skins/image/packs/my_stackchan_pack.cpp`
- Add: generated assets for `angry`, `doubt`, `sleepy`

- [ ] **Step 1: Add missing emotion assets**

Add these generated LVGL assets:

```text
my_stackchan_angry_*
my_stackchan_doubt_*
my_stackchan_sleepy_*
```

- [ ] **Step 2: Add expression entries**

Extend `kExpressions` in `my_stackchan_pack.cpp` with:

```cpp
{Emotion::Angry, &my_stackchan_angry_head, makeEyeSet(kAngryLeftEyes), makeEyeSet(kAngryRightEyes), makeMouthSet(kAngryMouths)},
{Emotion::Doubt, &my_stackchan_doubt_head, makeEyeSet(kDoubtLeftEyes), makeEyeSet(kDoubtRightEyes), makeMouthSet(kDoubtMouths)},
{Emotion::Sleepy, &my_stackchan_sleepy_head, makeEyeSet(kSleepyLeftEyes), makeEyeSet(kSleepyRightEyes), makeMouthSet(kSleepyMouths)},
```

- [ ] **Step 3: Re-run tests and build**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
cmake --build build-host-tests
ctest --test-dir build-host-tests --output-on-failure
idf.py build
```

Expected: tests and build pass.

- [ ] **Step 4: Commit**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan
git add firmware/main/stackchan/avatar/skins/image/packs
git commit -m "feat: add full image avatar expression pack"
```

## Task 9: Documentation And Git Closure

**Files:**
- Create: `firmware/docs/image-avatar.md`

- [ ] **Step 1: Document the asset contract**

Create `firmware/docs/image-avatar.md`:

```markdown
# ImageAvatar Asset Contract

ImageAvatar is an optional image-based avatar skin for StackChan.

Enable it with:

```text
StackChan Avatar -> Avatar Skin -> Image Avatar
```

The skin keeps the official avatar protocol:

- `leftEye`
- `rightEye`
- `mouth`
- `Emotion`
- speech bubble
- decorators
- modifiers

Assets are compiled as LVGL image descriptors and grouped by emotion.

Supported emotions:

- `neutral`
- `happy`
- `angry`
- `sad`
- `doubt`
- `sleepy`

Frame selection:

- eye and mouth `weight` is clamped to `0..100`
- weight selects a sprite frame from first to last
- position is clamped to `-100..100`
- position maps to the part-specific offset range

The default avatar remains available when `CONFIG_STACKCHAN_AVATAR_SKIN_DEFAULT` is selected.
```

- [ ] **Step 2: Run final verification**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan/firmware
cmake -S tests -B build-host-tests
cmake --build build-host-tests
ctest --test-dir build-host-tests --output-on-failure
idf.py build
```

Expected: all checks pass.

- [ ] **Step 3: Review diff for dead code**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan
git diff --stat main...HEAD
git diff main...HEAD -- firmware/main/stackchan/avatar/skins/image firmware/tests firmware/main/apps/app_avatar/app_avatar.cpp firmware/main/Kconfig.projbuild firmware/docs/image-avatar.md
```

Check:

```text
No unused generated assets.
No replacement of DefaultAvatar.
No App/Server protocol change.
No commented-out code blocks.
No broad refactor outside avatar skin wiring.
```

- [ ] **Step 4: Commit docs**

```bash
cd /Users/tianhaoxi/project/mcp/projects/StackChan
git add firmware/docs/image-avatar.md
git commit -m "docs: document image avatar asset contract"
```

## Final Definition Of Done

The work is complete only when all of these are true:

```text
Host tests pass.
Firmware build passes.
Device boots with DefaultAvatar when config is disabled.
Device boots with ImageAvatar when config is enabled.
Official app avatar control still works.
Official app dance control still works.
AI Agent speech still updates the speech bubble.
Speaking still moves mouth frames.
SetEmotion still maps neutral/happy/angry/sad/doubt/sleepy.
Touch/head-pet behavior still produces a livelier reaction.
The implementation is split into focused files.
No stale prototype code remains.
Changes are committed in logical commits.
```

## Recommended Follow-Up After First Version

After the first real-device pass, consider these as separate branches:

```text
1. Add App-side skin selection.
2. Add microSD runtime avatar pack loading.
3. Add custom image decorators beyond the official heart/sweat/angry/shy/dizzy decorators.
4. Add a small desktop asset preview tool.
```

Do not start those until the firmware-only image skin is verified on hardware.
