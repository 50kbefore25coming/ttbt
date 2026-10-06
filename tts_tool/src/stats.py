"""Thống kê nhanh: số từ, số câu (ước lượng), số ký tự."""
import re


def stats(text: str) -> dict:
    return {
        "từ": len(text.split()),
        "câu": len(re.findall(r"[.!?…]+(?=\s|$|[”\"’])", text)),
        "ký tự": len(text),
    }


def fmt(d: dict) -> str:
    return ", ".join(f"{k}: {v:,}" for k, v in d.items())
