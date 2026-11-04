import subprocess
import sys
from pathlib import Path


def _detect_language(video_path: Path) -> str:
    parent = video_path.parent.name.lower()
    if parent == "videos_en":
        return "en"
    elif parent == "videos_zh":
        return "zh"
    return "zh"


def _run_videocaptioner(args: list[str]) -> None:
    result = subprocess.run(
        ["videocaptioner", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"videocaptioner failed:\n{result.stdout}\n{result.stderr}")


def generate_bijian_srt(video_path: str | Path, out_path: str | Path | None = None) -> Path:
    video = Path(video_path).resolve()
    out = Path(out_path).resolve() if out_path else video.with_name(video.stem + ".bijian.srt")
    language = _detect_language(video)
    print(f"Transcribing {video.name} with bijian ASR (language={language}) ...")
    _run_videocaptioner(
        [
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
    )
    print(f"Generated {out}")
    return out


def generate_en_zh(en_srt: str | Path, out_path: str | Path | None = None) -> Path:
    src = Path(en_srt).resolve()
    if out_path:
        out = Path(out_path).resolve()
    elif src.name.endswith(".en.srt"):
        out = src.with_name(src.name.replace(".en.srt", "") + ".en-zh.srt")
    else:
        out = src.with_name(src.stem + ".en-zh.srt")
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

    output = video.with_suffix(".burned.mp4")
    subtitle_filter = (
        f"subtitles={srt}:"
        f"charenc=utf-8:"
        f"force_style='Fontsize=20,PrimaryColour=&HFFFFFF,BackColour=&H000000,"
        f"Bold=1,Outline=2,Shadow=1,BorderStyle=3,Alignment=2'"
    )

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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m video_captioner_subtitle.caption <video_path> [srt_path]")
        sys.exit(1)
    video = sys.argv[1]
    srt = sys.argv[2] if len(sys.argv) > 2 else None
    if srt and srt.endswith(".srt"):
        burn_subtitles(video, srt)
    else:
        bijian = generate_bijian_srt(video)
        en_zh = generate_en_zh(bijian)
        burn_subtitles(video, en_zh)
