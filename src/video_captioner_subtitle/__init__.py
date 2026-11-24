import sys


def main() -> None:
    """命令行入口：`video-captioner-subtitle [process <日期|视频>] ...`。

    无参数或 `process` 时委托给 ``caption.process`` 一键流程；
    传视频路径（可选 srt）时只烧录。
    """
    from . import caption

    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage:")
        print("  video-captioner-subtitle process <日期|视频> [--force]  一键流程")
        print("  video-captioner-subtitle <视频> [srt]                   仅烧录")
        return
    caption.main()


if __name__ == "__main__":
    main()
