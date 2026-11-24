"""从校正稿（完整句子）+ bijian 词级时间戳，生成句级 SRT。

思路：每段都是校正稿里一个完整句子（不按 ASR 分段切碎，从而翻译更自然、无残句），
句子起止时间取自 bijian 的**真实词级时间戳**（--word-timestamps），不是按字数估算。

用法: python -m video_captioner_subtitle.sentences <日期>
"""

import difflib
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from .apply_manual_texts import load_corrected_texts, write_srt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUBTITLES = PROJECT_ROOT / "subtitles"
SCRIPTS = PROJECT_ROOT / "scripts"

# 小数/缩写里的点不切（要求句点后必须空白+大写/数字/引号），中文句末标点直接切
_EN_SENT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\u201c\u2018])')
_CJK_SENT = re.compile(r"(?<=[。！？])")


def _parse_words(word_srt: Path) -> list[dict[str, Any]]:
    """解析词级 SRT，返回 [{'text','start','end'}]，时间为秒。"""
    out: list[dict[str, Any]] = []
    content = word_srt.read_text(encoding="utf-8")
    for block in re.split(r"\n\s*\n", content.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        m = re.match(
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})",
            lines[1],
        )
        if not m:
            continue
        g = list(map(int, m.groups()))
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        out.append({"text": " ".join(lines[2:]), "start": start, "end": end})
    return out


def _fmt(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    return (
        f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"
    )


def _split_sentences(text: str) -> list[str]:
    """按句子边界切分（支持中英文），合并无内容的空段。"""
    text = text.strip()
    if not text:
        return []
    sentences: list[str] = []
    for chunk in _CJK_SENT.split(text):
        chunk = chunk.strip()
        if not chunk:
            continue
        sentences.extend(s.strip() for s in _EN_SENT.split(chunk) if s and s.strip())
    return sentences


def _norm(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower(), flags=re.UNICODE)


def build_sentence_srt(word_srt: Path, md_path: Path, out_srt: Path) -> bool:
    """用校正稿整句 + 词级时间戳生成句级 SRT；内容不变则不写，返回是否改动。"""
    words = _parse_words(word_srt)
    if not words:
        raise RuntimeError(f"词级时间戳为空: {word_srt}")

    paragraphs = load_corrected_texts(md_path.stem)
    text = " ".join(paragraphs)
    sentences = _split_sentences(text)
    if not sentences:
        raise RuntimeError(f"校正稿没有有效句子: {md_path}")

    asr = [_norm(w["text"]) for w in words]
    corr: list[str] = []
    sid: list[int] = []
    for si, sent in enumerate(sentences):
        for tok in sent.split():
            corr.append(_norm(tok))
            sid.append(si)

    matcher = difflib.SequenceMatcher(None, asr, corr, autojunk=False)
    asr_of_corr: list[int | None] = [None] * len(corr)
    last = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                asr_of_corr[j1 + k] = i1 + k
                last = i1 + k
        elif tag == "replace":
            span = i2 - i1
            count = j2 - j1
            for k in range(count):
                idx = i1 + min(span - 1, int(round(span * k / max(1, count)))) if span else last
                asr_of_corr[j1 + k] = idx
                last = idx
        elif tag == "insert":
            for k in range(j1, j2):
                asr_of_corr[k] = last

    idx_by_sent: dict[int, list[int]] = defaultdict(list)
    for c_i, a_i in enumerate(asr_of_corr):
        if a_i is not None:
            idx_by_sent[sid[c_i]].append(a_i)

    # 先算有对齐的句子的起止，再为未对齐句子在相邻时间区间内插值
    spans: list[tuple[float, float] | None] = [None] * len(sentences)
    for si in range(len(sentences)):
        ids = idx_by_sent.get(si)
        if ids:
            spans[si] = (words[min(ids)]["start"], words[max(ids)]["end"])

    last_end = 0.0
    for si, spn in enumerate(spans):
        if spn is None:
            continue
        start, end = spn
        start = max(start, last_end)
        if end <= start:
            end = start + 0.6
        spans[si] = (start, end)
        last_end = end

    # 未对齐句子：用前一句结束到下一句开始之间插值，避免丢词
    for si, spn in enumerate(spans):
        if spn is not None:
            continue
        prev = spans[si - 1] if si > 0 else None
        prev_end = prev[1] if prev else last_end
        nxt_span = next((spans[j] for j in range(si + 1, len(spans)) if spans[j]), None)
        nxt = nxt_span[0] if nxt_span is not None else None
        start = prev_end
        end = nxt if nxt is not None and nxt > start else start + 0.6
        spans[si] = (start, end)

    segments = []
    for si, sent in enumerate(sentences):
        spn = spans[si]
        assert spn is not None
        start, end = spn
        segments.append({"index": si + 1, "start": _fmt(start), "end": _fmt(end), "text": sent})

    return write_srt(out_srt, segments)


def apply(date: str) -> Path:
    """从 subtitles/<日期>.word.srt + scripts/<日期>.md 生成句级 <日期>.bijian.srt。"""
    word_srt = SUBTITLES / f"{date}.word.srt"
    md_path = SCRIPTS / f"{date}.md"
    out_srt = SUBTITLES / f"{date}.bijian.srt"
    if not word_srt.is_file():
        raise FileNotFoundError(f"词级时间戳不存在: {word_srt}")
    if not md_path.is_file():
        raise FileNotFoundError(f"校正稿不存在: {md_path}")
    changed = build_sentence_srt(word_srt, md_path, out_srt)
    print(f"{'Built' if changed else 'No change'} sentence SRT -> {out_srt}")
    return out_srt


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m video_captioner_subtitle.sentences <日期>")
        sys.exit(1)
    try:
        apply(sys.argv[1])
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
