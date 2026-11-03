# 字幕烧录规则

所有字幕统一使用 `videocaptioner` 的 bijian ASR 生成时间戳（真实时间，非估算），
不要在代码里自行按字符比例估算时间轴。

时间模式：
- 默认（不加参数）输出**句级**分段，时间戳精确，用于字幕制作
- 加 `--word-timestamps` 输出**词级**分段（每词一条），用于时间轴锚点/单词集，
  不做字幕用

目录结构：
- `videos_en/`、`videos_zh/` — 源视频（`.mov` 等），不动
- `subtitles/` — 所有字幕文件（`.srt`）
- `burned/` — 所有烧录成片（`.burned.mp4`）
- `scripts/` — 人工审核用的校正文本

命名约定（放 `subtitles/` / `burned/` 下）：
- `<日期>.bijian.srt` — ASR 初稿 / 人工审核后的英文（或中文）字幕
- `<日期>.en-zh.srt` — 中英对照字幕
- `<日期>.word.srt` — 词级单词集（`--word-timestamps` 输出，仅作时间轴锚点/单词集）
- `<日期>.burned.mp4` — 烧录成片

## 英文视频（videos_en/ 下的视频）

1. **bijian 生成英文 SRT**（句级、真实时间戳），交人工审核：
   ```
   videocaptioner transcribe <视频> --asr bijian --language en --format srt -o subtitles/<日期>.bijian.srt
   ```
   用户审核后如有校正文本（如 scripts/ 下的脚本），用校正文本替换 SRT 的
   文字，**时间戳保持 bijian 原始值不变**。

2. **LLM 生成中英对照 SRT**：
   ```
   videocaptioner subtitle subtitles/<日期>.bijian.srt --translator llm --target-language zh-Hans --layout target-above --no-split --no-optimize -o subtitles/<日期>.en-zh.srt
   ```
   必须加 `--no-split --no-optimize`：
   - `--no-split`：禁止 LLM 跨段合并/重排，否则分段和时间戳错位、音画不同步
   - `--no-optimize`：禁止 LLM 改写英文，否则偏离审核过的文本

3. **烧录进视频**：
   ```
   videocaptioner synthesize <视频> -s subtitles/<日期>.en-zh.srt --subtitle-mode hard -o burned/<日期>.burned.mp4
   ```

## 中文视频（videos_zh/ 下的视频）

1. **bijian 生成中文 SRT**，必须经过人工审核才能烧录：
   ```
   videocaptioner transcribe <视频> --asr bijian --language zh --format srt -o subtitles/<日期>.bijian.srt
   ```
   审核后如有校正文本，用校正文本替换 SRT 文字，时间戳保持不变。

2. **烧录中文 SRT 进视频**：
   ```
   videocaptioner synthesize <视频> -s subtitles/<日期>.bijian.srt --subtitle-mode hard -o burned/<日期>.burned.mp4
   ```

## 代码封装

`src/video_captioner_subtitle/caption.py` 提供封装函数：
- `generate_bijian_srt(video, out_path)` — 第一步
- `generate_en_zh(en_srt, out_path)` — 第二步（内部须使用 `--no-split --no-optimize`）
- `burn_subtitles(video, srt_path)` — 烧录

### 一键流程（规划中，尚未实现）

- 待实现 `process_date(日期或视频路径)`：自动执行 转写 → 校正 → 翻译 → 校验 → 烧录，
  按命名约定落盘到 `subtitles/`、`burned/`
- 传日期自动定位 `videos_en/<日期>.mov`；传视频路径自动提取日期
- 命令行入口：`python -m video_captioner_subtitle.caption process <日期|视频路径>`
- 尚未实现前，请勿在流程中调用 `process_date`

