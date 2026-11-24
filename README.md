# Video Captioner Subtitle

<p align="right">
  <a href="./README.md">English</a> | <a href="./README.zh-CN.md">简体中文</a>
</p>

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
    caption.py             Wrapper functions + one-shot `process` pipeline
    sentences.py           Build whole-sentence SRT from reviewed script + word timings
    apply_manual_texts.py  (Alternative) align reviewed script into an existing SRT
```

## One-shot pipeline

```bash
python -m video_captioner_subtitle.caption process <date|video> [--force]
# alias: video-captioner-subtitle process <date|video> [--force]
```

Runs transcribe → whole-sentence alignment from the reviewed script (word-level
transcribe + `sentences`, if `scripts/<date>.md` exists) → translate (English videos)
→ burn, writing to the conventional paths. Existing outputs are skipped unless `--force`.

## Workflow

All commands are thin wrappers around `videocaptioner`. Timestamps come from the
bijian ASR (real, not estimated).

### English video (`videos_en/`)

1. **Transcribe** with word-level timestamps (`--word-timestamps`) to anchor real
   timings, and put the reviewed script in `scripts/<date>.md` (scene marker lines
   such as `**Hook**`, `HOOK (0-5s)`, `[HOOK]` are stripped automatically):

   ```bash
   videocaptioner transcribe videos_en/<date>.mov --asr bijian --language en \
       --format srt --word-timestamps -o subtitles/<date>.word.srt
   ```

2. **Whole-sentence SRT** — split the reviewed script into complete sentences and
   give each one its real start/end from the word timings, producing a
   sentence-level `subtitles/<date>.bijian.srt` (whole sentences, no fragments, real
   timestamps; idempotent):

   ```bash
   python -m video_captioner_subtitle.sentences <date>
   ```

   > Alternative: `python -m video_captioner_subtitle.apply_manual_texts <date>`
   > bridges the reviewed words back onto an existing sentence-level ASR segmentation
   > (keeps the ASR segments instead of whole sentences).

3. **Bilingual subtitles** — translate with LLM, preserving segments and
   timestamps:

   ```bash
   videocaptioner subtitle subtitles/<date>.bijian.srt --translator llm \
       --target-language zh-Hans --layout target-above --no-split --no-optimize \
       --batch-size 1 -o subtitles/<date>.en-zh.srt
   ```

   `--no-split --no-optimize --batch-size 1` are required: without them the LLM
   re-segments, rewrites the English, or merges short segments into a single
   request, desynchronising the subtitles. `--batch-size 1` forces a strict 1:1
   mapping (one request per segment), so the Chinese can never shift by a segment.

4. **Burn** — use `caption.burn_subtitles()` (auto CJK font), not
   `videocaptioner synthesize`:

   ```bash
   python -m video_captioner_subtitle.caption videos_en/<date>.mov \
       subtitles/<date>.en-zh.srt
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

- `generate_bijian_srt(video, out_path)` — transcribe
- `generate_en_zh(en_srt, out_path)` — translate (`--batch-size 1`)
- `burn_subtitles(video, srt_path)` — burn (auto CJK font)
- `process(target, force=False)` — one-shot pipeline

`src/video_captioner_subtitle/sentences.py`:

- `apply(date)` — build whole-sentence `subtitles/<date>.bijian.srt` from `subtitles/<date>.word.srt` + `scripts/<date>.md` (real word timestamps)

`src/video_captioner_subtitle/apply_manual_texts.py`:

- `apply(date)` — (alternative) align `scripts/<date>.md` into an existing `subtitles/<date>.bijian.srt`

## Requirements

- Python >= 3.12
- `videocaptioner` installed (`pip install videocaptioner`)
- For LLM translation: set the LLM API key/base/model via `videocaptioner config`
  (or `OPENAI_API_KEY` / `OPENAI_BASE_URL`)

---

<p align="right">
  <a href="./README.zh-CN.md">阅读中文版 / Read in Chinese</a>
</p>