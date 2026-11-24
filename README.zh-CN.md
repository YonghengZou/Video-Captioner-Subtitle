# Video Captioner Subtitle

<p align="right">
  <a href="./README.md">English</a> | <a href="./README.zh-CN.md">简体中文</a>
</p>

基于 [`videocaptioner`](https://github.com/kilocode/videocaptioner) 的字幕生成、
校正、翻译、烧录流水线（bijian ASR + LLM 翻译 + ffmpeg 烧录）。

## 目录结构

```
videos_en/      英文源视频（.mov）— 不纳入版本控制
videos_zh/      中文源视频（.mov）— 不纳入版本控制
subtitles/      所有 .srt 字幕 — 不纳入版本控制
scripts/        人工审核后的校正文本 — 不纳入版本控制
burned/         烧录成片（.burned.mp4）— 不纳入版本控制
src/video_captioner_subtitle/
    caption.py             流程封装 + 一键 `process`
    sentences.py           用校正稿整句 + 词级时间戳生成句级字幕
    apply_manual_texts.py  （备选）把校正稿对齐进既有 SRT
```

## 一键流程

```bash
python -m video_captioner_subtitle.caption process <日期|视频> [--force]
# 别名：video-captioner-subtitle process <日期|视频> [--force]
```

自动执行 转写 →（若有 `scripts/<日期>.md`）词级转写 + `sentences` 生成整句字幕 →
（英文视频）翻译 → 烧录，按命名约定落盘。产物已存在则跳过，加 `--force` 重新生成。

## 流程

所有命令都是 `videocaptioner` 的薄封装。时间戳来自 bijian ASR（真实时间，
非估算）。

### 英文视频（`videos_en/`）

1. **词级转写**（`--word-timestamps`，给每词真实时间做时间轴锚点），并把审核稿放
   `scripts/<日期>.md`（分镜标注行 `**Hook**`、`HOOK (0-5s)`、`[HOOK]` 等会自动剔除）：

   ```bash
   videocaptioner transcribe videos_en/<日期>.mov --asr bijian --language en \
       --format srt --word-timestamps -o subtitles/<日期>.word.srt
   ```

2. **生成整句字幕** — 按校正稿的完整句子切分，用词级时间戳给每句取真实起止时间，
   生成句级 `subtitles/<日期>.bijian.srt`（整句、不碎句、真实时间戳，幂等）：

   ```bash
   python -m video_captioner_subtitle.sentences <日期>
   ```

   > 备选：`python -m video_captioner_subtitle.apply_manual_texts <日期>` 会把校正稿
   > 按 ASR 词桥接填回既有分段（保留 ASR 分段，而非整句）。

3. **生成中英对照** — LLM 翻译，保持分段和时间戳：

   ```bash
   videocaptioner subtitle subtitles/<日期>.bijian.srt --translator llm \
       --target-language zh-Hans --layout target-above --no-split --no-optimize \
       --batch-size 1 -o subtitles/<日期>.en-zh.srt
   ```

   必须加 `--no-split --no-optimize --batch-size 1`：否则 LLM 会重新分段、改写英文，
   或把多段合并进一个请求，导致中文整体错位。`--batch-size 1` 强制每段单独翻译、
   一对一映射，中文不会再错位一段。

4. **烧录** — 用 `caption.burn_subtitles()`（自动中文字体），不要用
   `videocaptioner synthesize`：

   ```bash
   python -m video_captioner_subtitle.caption videos_en/<日期>.mov \
       subtitles/<日期>.en-zh.srt
   ```

### 中文视频（`videos_zh/`）

1. 用 `--language zh` 转写 → `subtitles/<日期>.bijian.srt`。
2. 必须经过人工审核才能烧录。
3. 直接烧录中文 SRT。

## 命名约定

| 模式 | 含义 |
| --- | --- |
| `<日期>.bijian.srt` | ASR 初稿 / 审核后的英文或中文字幕 |
| `<日期>.en-zh.srt` | 中英对照（中文在上、英文在下） |
| `<日期>.word.srt` | 词级单词集（`--word-timestamps`），仅作时间轴锚点 |
| `<日期>.burned.mp4` | 烧录成片 |

## 代码封装

`src/video_captioner_subtitle/caption.py`：

- `generate_bijian_srt(video, out_path)` — 转写
- `generate_en_zh(en_srt, out_path)` — 翻译（`--batch-size 1`）
- `burn_subtitles(video, srt_path)` — 烧录（自动中文字体）
- `process(target, force=False)` — 一键流程

`src/video_captioner_subtitle/sentences.py`：

- `apply(date)` — 用 `subtitles/<日期>.word.srt` + `scripts/<日期>.md` 生成整句级 `subtitles/<日期>.bijian.srt`（真实词级时间戳）

`src/video_captioner_subtitle/apply_manual_texts.py`：

- `apply(date)` — （备选）把 `scripts/<日期>.md` 对齐进既有 `subtitles/<日期>.bijian.srt`

## 环境要求

- Python >= 3.12
- 已安装 `videocaptioner`（`pip install videocaptioner`）
- LLM 翻译通过 `videocaptioner config` 设置 API key/base/model（或 `OPENAI_API_KEY` / `OPENAI_BASE_URL`）

## 说明

- 详细流程规则见 [`AGENTS.md`](./AGENTS.md)
- 有审核稿时用 `--word-timestamps` 词级转写 + `sentences` 生成整句字幕（默认流程）

---

<p align="right">
  <a href="./README.md">Read in English / 阅读英文版</a>
</p>
