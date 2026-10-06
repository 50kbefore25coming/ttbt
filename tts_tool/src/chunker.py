"""Cắt văn bản thành các đoạn <= limit ký tự, ưu tiên cắt theo đoạn rồi theo câu."""
import re

_SENT = re.compile(r"(?<=[.!?…”\"’])\s+")


def _hard_split(s: str, limit: int):
    out, cur = [], ""
    for w in s.split(" "):
        if cur and len(cur) + 1 + len(w) > limit:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_text(text: str, limit: int):
    pieces = []
    for par in text.split("\n"):
        par = par.strip()
        if not par:
            continue
        if len(par) <= limit:
            pieces.append(par)
            continue
        for sent in _SENT.split(par):
            pieces.extend([sent] if len(sent) <= limit else _hard_split(sent, limit))

    chunks, cur = [], ""
    for p in pieces:
        if cur and len(cur) + 1 + len(p) > limit:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return chunks
