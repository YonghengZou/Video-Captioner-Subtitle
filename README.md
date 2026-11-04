# Video Captioner Subtitle

Subtitle generation, correction, translation and burning pipeline built on top of
[`videocaptioner`](https://github.com/kilocode/videocaptioner) (bijian ASR + LLM
translation + ffmpeg burning).

## Directory layout

```
videos_en/      Source English videos (.mov) — not tracked
videos_zh/      Source Chinese videos (.mov) — not tracked
subtitles/      All .srt files — not tracked
scripts/        Human-reviewed correction text — not tracked
burned/         Burned videos (.burned.mp4) — not tracked
src/video_captioner_subtitle/
    caption.py  Wrapper functions for the pipeline
    align.py    WhisperX forced-alignment helpers
    siliconflow.py  SiliconFlow LLM client
```

## Workflow

All commands are thin wrappers around `videocaptioner`. Timestamps come from the
bijian ASR (real, not estimated).

### English video (`videos_en/`)

1. **Transcribe** (sentence-level, real timestamps) for human review:

   ```bash
   videocaptioner transcribe videos_en/<date>.mov --asr bijian --language en \
       --format srt -o subtitles/<date>.bijian.srt
   ```

2. **Review & correct** — replace the subtitle text with the reviewed script
   (`scripts/<date>.md`). **Keep the original timestamps.** Scene marker lines
   (e.g. `HOOK (0-5s)`, `SETUP`, `THE PROOF`, `CLOSE`) are not dialogue and must
   be stripped before mapping.

3. **Bilingual subtitles** — translate with LLM, preserving segments and
   timestamps:

   ```bash
   videocaptioner subtitle subtitles/<date>.bijian.srt --translator llm \
       --target-language zh-Hans --layout target-above --no-split --no-optimize \
       -o subtitles/<date>.en-zh.srt
   ```

   `--no-split --no-optimize` is required: without them the LLM re-segments and
   rewrites the English, desynchronising the subtitles.

4. **Burn**:

   ```bash
   videocaptioner synthesize videos_en/<date>.mov -s subtitles/<date>.en-zh.srt \
       --subtitle-mode hard -o burned/<date>.burned.mp4
   ```

### Chinese video (`videos_zh/`)

1. Transcribe with `--language zh` → `subtitles/<date>.bijian.srt`.
2. Must be human-reviewed before burning.
3. Burn the Chinese SRT directly.

## Naming convention

| Pattern | Meaning |
| --- | --- |
| `<date>.bijian.srt` | ASR draft / reviewed English or Chinese subtitle |
| `<date>.en-zh.srt` | Bilingual (Chinese above English) |
| `<date>.word.srt` | Word-level set (`--word-timestamps`), for timestamp anchors only |
| `<date>.burned.mp4` | Burned output |

## Code wrappers

`src/video_captioner_subtitle/caption.py`:

- `generate_bijian_srt(video, out_path)` — step 1
- `generate_en_zh(en_srt, out_path)` — step 2 (uses `--no-split --no-optimize`)
- `burn_subtitles(video, srt_path)` — step 3

## Requirements

- Python >= 3.12
- `videocaptioner` installed (`pip install videocaptioner`)
- For LLM translation: `SILICONFLOW_API_KEY` (or `OPENAI_API_KEY`) set in `.env`

## 中文摘要

本仓库是基于 `videocaptioner` 的字幕生成 → 校正 → 翻译 → 烧录流水线。

- **英文视频**：bijian 转写（句级真实时间戳）→ 人工审核（用 `scripts/<日期>.md` 替换文字、时间戳不动，剔除 HOOK/SETUP 等分镜标注行）→ LLM 生成中英对照（**必须 `--no-split --no-optimize`**）→ 烧录成片
- **中文视频**：bijian 中文转写 → 人工审核后烧录
- 详细规则见 [`AGENTS.MD`](./AGENTS.md)