# Video Captioner Subtitle

<p align="right">
  <b>English</b> | <a href="#中文">简体中文</a>
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
    caption.py  Pipeline wrapper functions
    align.py    WhisperX forced-alignment helpers
    siliconflow.py  SiliconFlow LLM client
```

## English workflow

Timestamps come from the bijian ASR (sentence-level, real—not estimated).
`--no-split --no-optimize` is required for translation: otherwise the LLM
re-segments and rewrites text, desynchronising the subtitles.

### English video (`videos_en/`)

1. **Transcribe** for human review:

   ```bash
   videocaptioner transcribe videos_en/<date>.mov --asr bijian --language en \
       --format srt -o subtitles/<date>.bijian.srt
   ```

2. **Review & correct** — replace the subtitle text with the reviewed script
   (`scripts/<date>.md`). **Keep the original timestamps.** Scene marker lines
   (e.g. `HOOK (0-5s)`, `SETUP`, `THE PROOF`, `CLOSE`) are not dialogue and must
   be stripped before mapping.

3. **Bilingual subtitles**:

   ```bash
   videocaptioner subtitle subtitles/<date>.bijian.srt --translator llm \
       --target-language zh-Hans --layout target-above --no-split --no-optimize \
       -o subtitles/<date>.en-zh.srt
   ```

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

## Requirements

- Python >= 3.12
- `videocaptioner` installed (`pip install videocaptioner`)
- For LLM translation: `SILICONFLOW_API_KEY` (or `OPENAI_API_KEY`) set in `.env`

---

<a id="中文"></a>

<details>
<summary><b>简体中文</b></summary>

## 中文说明

基于 [`videocaptioner`](https://github.com/kilocode/videocaptioner) 的字幕生成、
校正、翻译、烧录流水线（bijian ASR + LLM 翻译 + ffmpeg 烧录）。

### 目录结构

```
videos_en/      英文源视频（.mov）— 不纳入版本控制
videos_zh/      中文源视频（.mov）— 不纳入版本控制
subtitles/      所有 .srt 字幕 — 不纳入版本控制
scripts/        人工审核后的校正文本 — 不纳入版本控制
burned/         烧录成片（.burned.mp4）— 不纳入版本控制
src/video_captioner_subtitle/
    caption.py  流程封装函数
    align.py    WhisperX 强制对齐辅助
    siliconflow.py  SiliconFlow LLM 客户端
```

### 流程

所有命令都是 `videocaptioner` 的薄封装。时间戳来自 bijian ASR（真实时间，非估算）。

**英文视频（`videos_en/`）**

1. **转写**（句级、真实时间戳），交人工审核：

   ```bash
   videocaptioner transcribe videos_en/<日期>.mov --asr bijian --language en \
       --format srt -o subtitles/<日期>.bijian.srt
   ```

2. **审核校正** — 用校正稿（`scripts/<日期>.md`）替换字幕文字，
   **时间戳保持 bijian 原始值不变**。分镜标注行（如 `HOOK (0-5s)`、`SETUP`、
   `THE PROOF`、`CLOSE`）不是台词，映射前必须剔除。

3. **生成中英对照**：

   ```bash
   videocaptioner subtitle subtitles/<日期>.bijian.srt --translator llm \
       --target-language zh-Hans --layout target-above --no-split --no-optimize \
       -o subtitles/<日期>.en-zh.srt
   ```

   必须加 `--no-split --no-optimize`：否则 LLM 会重新分段并改写英文，导致音画不同步。

4. **烧录**：

   ```bash
   videocaptioner synthesize videos_en/<日期>.mov -s subtitles/<日期>.en-zh.srt \
       --subtitle-mode hard -o burned/<日期>.burned.mp4
   ```

**中文视频（`videos_zh/`）**

1. 用 `--language zh` 转写 → `subtitles/<日期>.bijian.srt`。
2. 必须经过人工审核才能烧录。
3. 直接烧录中文 SRT。

### 命名约定

| 模式 | 含义 |
| --- | --- |
| `<日期>.bijian.srt` | ASR 初稿 / 审核后的英文或中文字幕 |
| `<日期>.en-zh.srt` | 中英对照（中文在上、英文在下） |
| `<日期>.word.srt` | 词级单词集（`--word-timestamps`），仅作时间轴锚点 |
| `<日期>.burned.mp4` | 烧录成片 |

### 代码封装

`src/video_captioner_subtitle/caption.py`：

- `generate_bijian_srt(video, out_path)` — 第一步
- `generate_en_zh(en_srt, out_path)` — 第二步（使用 `--no-split --no-optimize`）
- `burn_subtitles(video, srt_path)` — 第三步

### 环境要求

- Python >= 3.12
- 已安装 `videocaptioner`（`pip install videocaptioner`）
- LLM 翻译需在 `.env` 中设置 `SILICONFLOW_API_KEY`（或 `OPENAI_API_KEY`）

### 补充

- 完整流程规则见 [`AGENTS.md`](./AGENTS.md)
- 词级锚定（`--word-timestamps`）只在句级时间戳明显漂移时按需使用，不是流程必选项

</details>
