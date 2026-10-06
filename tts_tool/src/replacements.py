"""Quy tắc thay thế cố định (không dùng AI), đọc từ replacements.txt.

Mỗi dòng:  mẫu_regex => chuỗi_thay_thế      (dòng bắt đầu bằng # là chú thích)
Áp dụng sau bước xoá (n), trước bước AI. Mỗi lần thay đều được ghi log.
"""
import re
from pathlib import Path


def load_replacements(path):
    rules = []
    p = Path(path)
    if not p.exists():
        return rules
    for n, line in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if " => " not in line:
            raise ValueError(f"{p.name} dòng {n}: thiếu ' => ' ({line!r})")
        pat, rep = line.split(" => ", 1)
        try:
            rules.append((re.compile(pat), rep, line))
        except re.error as e:
            raise ValueError(f"{p.name} dòng {n}: regex sai ({e})")
    return rules


def apply_replacements(text, rules):
    log = []
    for rx, rep, raw in rules:
        text, n = rx.subn(rep, text)
        if n:
            log.append(f"[THAY THẾ x{n}] {raw}")
    return text, log
