"""把 scripts/<日期>.md 的人工校正文本对齐并替换到 subtitles/<日期>.bijian.srt。

对齐方式：以 bijian 原始 ASR 各段文本为“桥梁”，把整篇校正稿拆成词后与 ASR 词序列
做 difflib 序列对齐，使每个校正词落到其对应 ASR 词所在的分段。这样分段边界沿用
bijian 真实时间戳，不按字数比例硬切，也就不会出现把一句话切碎的碎段。
时间戳完全不改。

用法: python -m video_captioner_subtitle.apply_manual_texts <日期>
"""
import difflib
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUBTITLES = PROJECT_ROOT / "subtitles"
SCRIPTS = PROJECT_ROOT / "scripts"

# 分镜标注行：行首为 [HOOK] / HOOK (0-5s) / **Hook** 等，不是台词，剔除
_SHOT_LINE = re.compile(
    r"^\s*(\*{0,2}\s*)?(HOOK|SETUP|THE PROOF|CLOSE|BODY|TAKEAWAY|CAVEAT|"
    r"HONEST CAVEAT|WHAT'S A LOOPED TRANSFORMER|WHAT GLM-5\.4 DOES|"
    r"THE CATCH|THE CLAIMS|AVAILABILITY)\b.*$",
    re.IGNORECASE,
)


def load_corrected_texts(date: str) -> list[str]:
    """读取 scripts/<日期>.md，剔除分镜标注行，合并连续正文为段落列表。"""
    md_path = SCRIPTS / f"{date}.md"
    paragraphs: list[str] = []
    current: list[str] = []
    for raw in md_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if _SHOT_LINE.match(line):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def parse_srt(srt_path: str | Path) -> list[dict]:
    """解析 SRT，返回 [{'index','start','end','text'}, ...]。"""
    content = Path(srt_path).read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", content.strip())
    segments = []
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        index = int(lines[0])
        timing = lines[1]
        text = "\n".join(lines[2:])
        m = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
            timing,
        )
        if not m:
            continue
        segments.append(
            {"index": index, "start": m.group(1), "end": m.group(2), "text": text}
        )
    return segments


def render_srt(segments: list[dict]) -> str:
    blocks = []
    for seg in segments:
        blocks.append(
            f"{seg['index']}\n{seg['start']} --> {seg['end']}\n{seg['text']}\n"
        )
    return "\n".join(blocks)


def write_srt(srt_path: Path, segments: list[dict]) -> bool:
    """写入 SRT；内容与现有文件一致时不写，返回是否发生了改动。"""
    content = render_srt(segments)
    if srt_path.is_file() and srt_path.read_text(encoding="utf-8") == content:
        return False
    srt_path.write_text(content, encoding="utf-8")
    return True


def _norm(word: str) -> str:
    """归一化词：小写、去标点，仅保留字母数字。"""
    return re.sub(r"[^0-9a-z]", "", word.lower())


def _align_corrected(segments: list[dict], paragraphs: list[str]) -> list[int]:
    """把校正词分配到各 SRT 分段，返回每个校正词的段索引映射。"""
    asr_tokens: list[str] = []
    asr_seg_ids: list[int] = []
    for seg in segments:
        for tok in seg["text"].split():
            asr_tokens.append(tok)
            asr_seg_ids.append(seg["index"])

    corr_tokens = " ".join(paragraphs).split()
    if not asr_tokens or not corr_tokens:
        raise RuntimeError("ASR 或校正文本为空，无法对齐")

    asr_norm = [_norm(t) for t in asr_tokens]
    corr_norm = [_norm(t) for t in corr_tokens]

    matcher = difflib.SequenceMatcher(None, asr_norm, corr_norm, autojunk=False)
    seg_of_corr: list[int | None] = [None] * len(corr_tokens)
    last_seg = asr_seg_ids[0]

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                seg_id = asr_seg_ids[i1 + k]
                seg_of_corr[j1 + k] = seg_id
                last_seg = seg_id
        elif tag == "replace":
            span = i2 - i1
            count = j2 - j1
            if span == 0:
                for k in range(count):
                    seg_of_corr[j1 + k] = last_seg
                continue
            for k in range(count):
                pos = i1 + min(span - 1, int(round(span * k / max(1, count))))
                seg_id = asr_seg_ids[pos]
                seg_of_corr[j1 + k] = seg_id
                last_seg = seg_id
        elif tag == "insert":
            for k in range(j1, j2):
                seg_of_corr[k] = last_seg
        # delete: ASR 有词、校正无对应，忽略

    return seg_of_corr


def align_corrected(segments: list[dict], paragraphs: list[str]) -> list[int]:
    """按 ASR 桥梁对齐，把校正词写回各分段；返回未被分配校正词的段索引列表。"""
    if not paragraphs:
        raise RuntimeError("校正稿为空")
    corr_tokens = " ".join(paragraphs).split()
    seg_of_corr = _align_corrected(segments, paragraphs)

    by_seg: dict[int, list[str]] = {seg["index"]: [] for seg in segments}
    last_seg = segments[0]["index"]
    for tok, seg_id in zip(corr_tokens, seg_of_corr):
        if seg_id is None:
            seg_id = last_seg
        by_seg[seg_id].append(tok)
        last_seg = seg_id

    empty: list[int] = []
    for seg in segments:
        toks = by_seg[seg["index"]]
        if toks:
            seg["text"] = " ".join(toks)
        else:
            # 该段没有分到校正词：保留原 ASR 文本兜底
            empty.append(seg["index"])
    return empty


def apply(date: str) -> Path:
    """把 scripts/<日期>.md 对齐写入 subtitles/<日期>.bijian.srt（原地替换）。"""
    md_path = SCRIPTS / f"{date}.md"
    if not md_path.is_file():
        raise FileNotFoundError(f"校正稿不存在: {md_path}")
    srt_path = SUBTITLES / f"{date}.bijian.srt"
    if not srt_path.is_file():
        raise FileNotFoundError(f"SRT 不存在: {srt_path}")

    paragraphs = load_corrected_texts(date)
    if not paragraphs:
        raise RuntimeError(f"{md_path} 中未找到正文段落")

    segments = parse_srt(srt_path)
    empty = align_corrected(segments, paragraphs)
    changed = write_srt(srt_path, segments)
    if changed:
        print(f"Applied corrected text to {len(segments)} segments -> {srt_path}")
    else:
        print(f"No change (already aligned): {srt_path}")
    if empty:
        print(f"WARNING: 以下分段未匹配到校正词，保留 ASR 原文: {empty}")
    return srt_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m video_captioner_subtitle.apply_manual_texts <日期>")
        sys.exit(1)
    try:
        apply(sys.argv[1])
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()