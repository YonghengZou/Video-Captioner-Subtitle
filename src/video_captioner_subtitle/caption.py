import subprocess
import sys
from pathlib import Path

from .sentences import apply as build_sentences

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUBTITLES_DIR = PROJECT_ROOT / "subtitles"
BURNED_DIR = PROJECT_ROOT / "burned"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
VIDEOS_EN_DIR = PROJECT_ROOT / "videos_en"
VIDEOS_ZH_DIR = PROJECT_ROOT / "videos_zh"
_VIDEO_EXTS = (".mov", ".mp4", ".m4v", ".mkv", ".webm")


def _paths(date: str) -> dict[str, Path]:
    """按日期统一推导各产物路径（命名约定的唯一真源）。"""
    return {
        "bijian": SUBTITLES_DIR / f"{date}.bijian.srt",
        "word": SUBTITLES_DIR / f"{date}.word.srt",
        "en_zh": SUBTITLES_DIR / f"{date}.en-zh.srt",
        "burned": BURNED_DIR / f"{date}.burned.mp4",
        "script": SCRIPTS_DIR / f"{date}.md",
    }


def _is_fresh(out: Path, *sources: Path) -> bool:
    """out 存在且不早于所有 sources 时视为最新。"""
    if not out.is_file():
        return False
    out_mtime = out.stat().st_mtime
    return all(out_mtime >= src.stat().st_mtime for src in sources if src.is_file())


# 系统中文字体优先级列表（macOS / Linux 通用，按常见度排序）
_CJK_FONT_CANDIDATES = [
    "Hiragino Sans GB",
    "PingFang SC",
    "Heiti SC",
    "STHeiti",
    "SimHei",
    "Noto Sans CJK SC",
    "WenQuanYi Zen Hei",
    "Source Han Sans SC",
    "Microsoft YaHei",
]


def _detect_language(video_path: Path) -> str:
    parent = video_path.parent.name.lower()
    if parent == "videos_en":
        return "en"
    elif parent == "videos_zh":
        return "zh"
    return "zh"


def _list_system_fonts() -> list[str]:
    """通过 fc-list 列出系统已安装字体的 family 名称。"""
    try:
        result = subprocess.run(["fc-list", ":family"], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []
        fonts: list[str] = []
        for line in result.stdout.splitlines():
            for part in line.split(","):
                name = part.strip().strip('"')
                if name and name not in fonts:
                    fonts.append(name)
        return fonts
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def _detect_cjk_font() -> str | None:
    """在系统已安装字体中查找第一个可用的中文字体，找不到返回 None。"""
    installed = _list_system_fonts()
    if not installed:
        return None
    installed_lower = {f.lower() for f in installed}
    for candidate in _CJK_FONT_CANDIDATES:
        if candidate.lower() in installed_lower:
            return candidate
    # 兜底：只要 family 名中含 CJK 字符，就认为系统有中文字体
    for name in installed:
        for ch in name:
            if "\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u303f":
                return "Hiragino Sans GB"
    return None


def _srt_contains_cjk(srt_path: str | Path) -> bool:
    """判断 SRT 文本中是否含有 CJK 字符。"""
    try:
        text = Path(srt_path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u303f":
            return True
    return False


def _build_subtitle_filter(srt: Path) -> str:
    """构造 ffmpeg subtitles 滤镜参数，自动选择中文字体。"""
    font = _detect_cjk_font() if _srt_contains_cjk(srt) else None
    if font:
        # 转义 ASS force_style 中的特殊字符（逗号、冒号、分号）
        safe_font = font.replace(",", "\\,").replace(":", "\\:").replace(";", "\\;")
        font_style = f"Fontname={safe_font},"
    else:
        font_style = ""
    return (
        f"subtitles={srt}:"
        f"charenc=utf-8:"
        f"force_style='{font_style}Fontsize=16,"
        f"PrimaryColour=&HFFFFFF,BackColour=&H000000,"
        f"Bold=1,Outline=2,Shadow=1,BorderStyle=3,Alignment=2'"
    )


def _run_videocaptioner(args: list[str]) -> None:
    result = subprocess.run(
        ["videocaptioner", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"videocaptioner failed:\n{result.stdout}\n{result.stderr}")


def generate_bijian_srt(
    video_path: str | Path,
    out_path: str | Path | None = None,
    word_timestamps: bool = False,
) -> Path:
    video = Path(video_path).resolve()
    SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)
    if out_path:
        out = Path(out_path).resolve()
    elif word_timestamps:
        out = _paths(video.stem)["word"]
    else:
        out = _paths(video.stem)["bijian"]
    language = _detect_language(video)
    kind = "word-level" if word_timestamps else "sentence-level"
    print(f"Transcribing {video.name} with bijian ASR ({kind}, language={language}) ...")
    args = [
        "transcribe",
        str(video),
        "--asr",
        "bijian",
        "--language",
        language,
        "--format",
        "srt",
        "-o",
        str(out),
    ]
    if word_timestamps:
        args.append("--word-timestamps")
    _run_videocaptioner(args)
    print(f"Generated {out}")
    return out


def generate_en_zh(en_srt: str | Path, out_path: str | Path | None = None) -> Path:
    src = Path(en_srt).resolve()
    date = src.name.replace(".bijian.srt", "").replace(".en.srt", "")
    date = date.replace(".srt", "")
    SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(out_path).resolve() if out_path else _paths(date)["en_zh"]
    print(f"Optimizing and translating {src.name} with LLM ...")
    _run_videocaptioner(
        [
            "subtitle",
            str(src),
            "--translator",
            "llm",
            "--target-language",
            "zh-Hans",
            "--layout",
            "target-above",
            "--no-split",
            "--no-optimize",
            "--batch-size",
            "1",
            "-o",
            str(out),
        ]
    )
    print(f"Generated {out}")
    return out


def burn_subtitles(video_path: str | Path, srt_path: str | Path | None = None) -> Path:
    video = Path(video_path).resolve()
    srt = Path(srt_path).resolve() if srt_path else video.with_suffix(".srt")

    if not srt.is_file():
        raise FileNotFoundError(f"SRT file not found: {srt}")

    burned_dir = BURNED_DIR
    burned_dir.mkdir(parents=True, exist_ok=True)
    output = burned_dir / f"{video.stem}.burned.mp4"
    subtitle_filter = _build_subtitle_filter(srt)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video),
        "-vf",
        subtitle_filter,
        "-c:a",
        "copy",
        str(output),
    ]
    print(f"Burning subtitles into {output.name} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr}")
    print(f"Generated {output}")
    return output


def _resolve_target(target: str | Path) -> tuple[str, Path, str]:
    """把「日期」或「视频路径」解析为 (日期, 视频路径, 语言)。"""
    p = Path(target)
    if p.suffix.lower() in _VIDEO_EXTS and p.is_file():
        video = p.resolve()
        return video.stem, video, _detect_language(video)
    # 当作日期：在 videos_en / videos_zh 中查找
    date = str(target)
    for directory, language in ((VIDEOS_EN_DIR, "en"), (VIDEOS_ZH_DIR, "zh")):
        for ext in _VIDEO_EXTS:
            candidate = directory / f"{date}{ext}"
            if candidate.is_file():
                return date, candidate.resolve(), language
    raise FileNotFoundError(
        f"找不到日期 {date} 对应的视频（videos_en/ 或 videos_zh/ 下 *{_VIDEO_EXTS}）"
    )


def process(target: str | Path, force: bool = False) -> Path:
    """一键流程：转写 → 对齐校正稿（若有）→ 翻译（英文视频）→ 烧录。

    target 可为日期（如 2026-11-23）或视频路径。产物已存在时默认跳过；
    force=True 则重新生成。返回烧录成片路径。
    """
    date, video, language = _resolve_target(target)
    paths = _paths(date)
    print(f"== process {date} ({language}) ==")

    # 1. 转写
    if paths["script"].is_file():
        # 有校正稿：词级转写 + 用整句生成句级 SRT（真实词级时间戳）
        if force or not paths["word"].is_file():
            generate_bijian_srt(video, paths["word"], word_timestamps=True)
        else:
            print(f"skip word-transcribe (exists): {paths['word']}")
        build_sentences(date)
    else:
        # 无校正稿：普通句级转写
        if force or not paths["bijian"].is_file():
            generate_bijian_srt(video, paths["bijian"])
        else:
            print(f"skip transcribe (exists): {paths['bijian']}")

    # 2. 翻译（英文视频：生成中英对照，整句烧录）
    if language == "en":
        if force or not _is_fresh(paths["en_zh"], paths["bijian"]):
            generate_en_zh(paths["bijian"], paths["en_zh"])
        else:
            print(f"skip translate (up-to-date): {paths['en_zh']}")
        burn_srt = paths["en_zh"]
    else:
        burn_srt = paths["bijian"]

    # 3. 烧录（成片比字幕新则跳过）
    if not force and _is_fresh(paths["burned"], burn_srt):
        print(f"skip burn (up-to-date): {paths['burned']}")
        return paths["burned"]
    return burn_subtitles(video, burn_srt)


def main() -> None:
    """命令行入口：process <日期|视频> [--force] 或 <视频> [srt]（仅烧录）。"""
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if a != "--force"]
    if not args:
        print(
            "Usage:\n"
            "  python -m video_captioner_subtitle.caption process <日期|视频> [--force]\n"
            "  python -m video_captioner_subtitle.caption <视频> [srt]  # 仅烧录"
        )
        sys.exit(1)
    if args[0] == "process":
        if len(args) < 2:
            print("ERROR: 缺少日期或视频路径")
            sys.exit(1)
        process(args[1], force=force)
    elif len(args) >= 2 and args[1].endswith(".srt"):
        burn_subtitles(args[0], args[1])
    else:
        process(args[0], force=force)


if __name__ == "__main__":
    main()
