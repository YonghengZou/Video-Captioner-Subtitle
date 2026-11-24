## Python 环境

Python 环境由 `uv` 管理，使用 `.venv`。运行代码时用 `uv run` 或激活 `.venv`。

LLM 翻译使用 `videocaptioner` 配置的模型（`~/Library/Application Support/VideoCaptioner/config.toml` 的 `[llm]`）。本项目推荐 SiliconFlow 的 `deepseek-ai/DeepSeek-V4.1-Flash`：英译中准确（vision→视觉能力、live→上线 等歧义词正确）、速度快、费用极低；7B 级小模型（如 Qwen2.5-7B）会残留英文/错译，不建议。

所有字幕统一使用 `videocaptioner` 的 bijian ASR 生成时间戳（真实时间，非估算），
不要在代码里自行按字符比例估算时间轴。

时间模式：
- 默认（不加参数）输出**句级**分段，时间戳精确，用于一般字幕
- 加 `--word-timestamps` 输出**词级**分段（每词一条，真实时间）。**有校正稿时用它**：
  取校正稿的完整句子，用词级时间戳给每句定界，生成“整句 + 真实时间”的句级字幕
  （完整句子翻译自然、不碎句，见 `sentences.py`）

目录结构：
- `videos_en/`、`videos_zh/` — 源视频（`.mov` 等），不动
- `subtitles/` — 所有字幕文件（`.srt`）
- `burned/` — 所有烧录成片（`.burned.mp4`）
- `scripts/` — 人工审核用的校正文本

命名约定（放 `subtitles/` / `burned/` 下）：
- `<日期>.bijian.srt` — 人工审核后的英文（或中文）字幕（有校正稿时为整句级）
- `<日期>.en-zh.srt` — 中英对照字幕
- `<日期>.word.srt` — 词级时间戳（`--word-timestamps` 输出，用于给整句定界）
- `<日期>.burned.mp4` — 烧录成片

## 英文视频（videos_en/ 下的视频）

1. **转写 + 整句校正**：
   ```
   videocaptioner transcribe <视频> --asr bijian --language en --format srt --word-timestamps -o subtitles/<日期>.word.srt
   python -m video_captioner_subtitle.sentences <日期>
   ```
   人工审核稿放 `scripts/<日期>.md`（分镜稿格式，含 `**Hook**` / `HOOK (0-5s)` / `[HOOK]` 等分镜标注行，不是台词，自动剔除）。`sentences` 按校正稿的**完整句子**切分，用词级时间戳给每句取真实起止时间，生成 `subtitles/<日期>.bijian.srt`（句级、整句、真实时间戳）。不按字数估算、不把句子切碎，幂等。

2. **LLM 生成中英对照 SRT**：
   ```
   videocaptioner subtitle subtitles/<日期>.bijian.srt --translator llm --target-language zh-Hans --layout target-above --no-split --no-optimize --batch-size 1 -o subtitles/<日期>.en-zh.srt
   ```
   必须加这些参数：
   - `--no-split`：禁止 LLM 跨段合并/重排，否则分段和时间戳错位、音画不同步
   - `--no-optimize`：禁止 LLM 改写英文，否则偏离审核过的文本
   - `--batch-size 1`：**必须**。默认 batch=20 会把多段塞进一个请求，LLM 会把短句跨段合并挪位，导致中文整体错位一段（校验只查 key 齐全、不查语义对位）。设 1 即每段单独翻译，强制一对一，对位正确
   - `--batch-size 1` 的代价：单段独立翻译丢了上下文，个别断句的用词可能略生硬，可人工润色，但位置不会再错

3. **烧录进视频**：统一用 `caption.burn_subtitles()`（内部调用 ffmpeg 的 `subtitles` 滤镜，`-c:a copy`）：
   ```
   python -m video_captioner_subtitle.caption <视频> subtitles/<日期>.en-zh.srt
   ```
   烧录时必须指定中文字体，否则中文显示为乱码。`burn_subtitles()` 已内置自动检测：通过 `fc-list` 查找系统中文字体（Hiragino Sans GB / PingFang SC / Heiti SC / SimHei / Noto Sans CJK SC 等），SRT 含 CJK 字符时自动注入 `Fontname=...`，纯英文 SRT 不加。不要用 `videocaptioner synthesize`（不注入中文字体，中文会乱码）。

## 中文视频（videos_zh/ 下的视频）

1. **bijian 生成中文 SRT**，必须经过人工审核才能烧录：
   ```
   videocaptioner transcribe <视频> --asr bijian --language zh --format srt -o subtitles/<日期>.bijian.srt
   ```
   审核稿放 `scripts/<日期>.md` 时同样用 `--word-timestamps` + `python -m video_captioner_subtitle.sentences <日期>` 生成整句级中文 SRT（见英文流程第 1 步）。

2. **烧录中文 SRT 进视频**：用 `caption.burn_subtitles()`（自动中文字体）：
   ```
   python -m video_captioner_subtitle.caption <视频> subtitles/<日期>.bijian.srt
   ```

## 代码封装

`src/video_captioner_subtitle/caption.py` 提供封装函数：
- `generate_bijian_srt(video, out_path, word_timestamps=False)` — 转写（默认落 `.bijian.srt`；`word_timestamps=True` 落 `.word.srt`）
- `generate_en_zh(en_srt, out_path)` — 翻译（默认落 `subtitles/<日期>.en-zh.srt`，内部 `--batch-size 1`）
- `burn_subtitles(video, srt_path)` — 烧录（输出落 `burned/<日期>.burned.mp4`，自动中文字体）
- `process(target, force=False)` — 一键流程

`src/video_captioner_subtitle/sentences.py`：
- `apply(date)` — 用 `subtitles/<日期>.word.srt` + `scripts/<日期>.md` 生成整句级 `subtitles/<日期>.bijian.srt`（真实词级时间戳）

`src/video_captioner_subtitle/apply_manual_texts.py`：
- `apply(date)` — 旧方案：把校正稿按 ASR 词桥接填回既有分段（保留 ASR 分段，见备选）

### 一键流程（已实现）

```
python -m video_captioner_subtitle.caption process <日期|视频路径> [--force]
```

- 有 `scripts/<日期>.md`：词级转写 → `sentences` 生成整句级 `.bijian.srt` →（英文视频）翻译 → 烧录
- 无校正稿：普通句级转写 →（英文视频）翻译 → 烧录
- 传日期自动定位 `videos_en/` 或 `videos_zh/` 下的视频；传视频路径自动提取日期
- 产物已存在/更新则跳过；加 `--force` 重新生成全部
- 所有路径由 `_paths(date)` 统一推导，无需手动 mv
- 命令行别名：`video-captioner-subtitle process <日期|视频> [--force]`

