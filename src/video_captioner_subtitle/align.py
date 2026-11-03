import re
import subprocess
from pathlib import Path

import whisperx


def _format_ts(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    h = total_ms // 3_600_000
    m = (total_ms % 3_600_000) // 60_000
    s = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _extract_audio(video_path: Path, out_path: Path | None = None) -> Path:
    video = Path(video_path).resolve()
    audio = Path(out_path).resolve() if out_path else video.with_suffix(".wav")
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(audio),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed:\n{result.stderr}")
    return audio


def _clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_into_sentences(text: str) -> list[str]:
    text = text.strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def align_text_to_audio(
    video_path: str | Path,
    text: str,
    language: str = "en",
    out_path: str | Path | None = None,
) -> Path:
    """Force-align reviewed text to audio and write a precise SRT.

    Uses whisperx transcription + word-level alignment to get accurate
    timestamps for the given (already reviewed) text, then groups aligned
    words into segments matching the sentence structure of ``text``.
    """
    video = Path(video_path).resolve()
    out = Path(out_path).resolve() if out_path else video.with_name(video.stem + ".aligned.srt")

    audio = _extract_audio(video)
    try:
        device = "cpu"
        model = whisperx.load_model("large-v2", device=device, language=language)
        result = model.transcribe(str(audio))
        lang = result.get("language", language)

        model_a, metadata = whisperx.load_align_model(language_code=lang, device=device)
        result = whisperx.align(result["segments"], model_a, metadata, str(audio), device=device)

        # Build a flat list of aligned words: [(word, start, end), ...]
        words: list[tuple[str, float, float]] = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                word = w.get("word", "").strip()
                start = w.get("start")
                end = w.get("end")
                if word and start is not None and end is not None:
                    words.append((word, float(start), float(end)))

        if not words:
            raise RuntimeError("whisperx alignment produced no words")

        # Split reviewed text into sentences
        sentences = _split_into_sentences(text)
        if not sentences:
            sentences = [text]

        # Map cleaned reviewed words to aligned word timestamps
        aligned_words = [_clean_text(w) for w, _, _ in words]
        srt_blocks: list[str] = []
        idx = 0
        segment_no = 1

        for sentence in sentences:
            sent_words = _clean_text(sentence).split()
            if not sent_words:
                continue
            start_sec = None
            end_sec = None
            matched = 0
            while idx < len(aligned_words) and matched < len(sent_words):
                if aligned_words[idx] == sent_words[matched]:
                    if start_sec is None:
                        start_sec = words[idx][1]
                    end_sec = words[idx][2]
                    matched += 1
                idx += 1
            if start_sec is None:
                # Fallback: skip this sentence
                continue
            srt_blocks.append(
                f"{segment_no}\n{_format_ts(start_sec)} --> {_format_ts(end_sec)}\n{sentence}\n"
            )
            segment_no += 1

        out.write_text("\n".join(srt_blocks) + "\n", encoding="utf-8")
        print(f"Aligned SRT generated: {out}")
        return out
    finally:
        if audio.exists():
            audio.unlink(missing_ok=True)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m video_captioner_subtitle.align <video_path> <text_path> [out_path]")
        sys.exit(1)
    video = sys.argv[1]
    text_path = sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) > 3 else None
    text = Path(text_path).read_text(encoding="utf-8")
    align_text_to_audio(video, text, out_path=out_path)
