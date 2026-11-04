import sys

from . import caption


def main() -> None:
    """Command-line entry point: `video-captioner-subtitle <video|process> ...`.

    Delegates to ``caption.py``; the full one-shot pipeline
    (``process <日期|视频路径>``) is planned but not yet implemented.
    """
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage:")
        print("  video-captioner-subtitle <video> [srt]        burn subtitles into video")
        print("  video-captioner-subtitle process <date|video> full pipeline (planned)")
        return
    if args[0] == "process":
        print("process <日期|视频路径> is not yet implemented.")
        return
    caption.main()
