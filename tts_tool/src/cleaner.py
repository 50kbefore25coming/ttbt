"""Bước 1 (chắc chắn, không dùng AI): xoá số chú thích (n), chuẩn hoá khoảng trắng.

Chỉ xoá đúng dạng ngoặc tròn chứa 1-3 chữ số: (1), (23).
Không đụng tới (Hoa Sơn), (1945), [ghi chú]...
Mỗi chỗ xoá đều được ghi log kèm ngữ cảnh để bạn kiểm tra.
"""
import re
import unicodedata

# Ăn luôn khoảng trắng đứng trước dấu, để không còn dấu cách thừa.
MARK = re.compile(r"[ \t]*\(\s*\d{1,3}\s*\)")
FOOTNOTE_LINE = re.compile(r"^[ \t]*\(\s*\d{1,3}\s*\)[ \t]+\S.*$", re.M)
SENT_END = ".!?…”\"’"


def _ctx(s: str) -> str:
    return s.replace("\n", "⏎")


def clean(text: str, strip_footnote_lines: bool = False, normalize_ellipsis: bool = True):
    """Trả về (văn_bản_sạch, log)."""
    log = []
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")

    if strip_footnote_lines:
        def drop_line(m):
            log.append(f"[DÒNG CHÚ THÍCH] {_ctx(m.group().strip()[:100])}")
            return ""
        text = FOOTNOTE_LINE.sub(drop_line, text)

    src = text  # giữ bản gốc để lấy ngữ cảnh chính xác

    def repl(m):
        s, e = m.start(), m.end()
        before = src[s - 1] if s > 0 else ""
        after = src[e] if e < len(src) else ""
        log.append(
            f"...{_ctx(src[max(0, s - 25):s])}[{m.group().strip()}]{_ctx(src[e:e + 25])}..."
        )
        # "đi.(1)“Nếu" -> "đi. “Nếu" ; "abc(1)def" -> "abc def"
        if before and after and not after.isspace():
            if before in SENT_END and after not in ".,;:!?…”\")":
                return " "
            if before.isalnum() and after.isalnum():
                return " "
        return ""

    text = MARK.sub(repl, text)

    if normalize_ellipsis:
        text = re.sub(r"\.{4,}", "...", text)   # ".........." -> "..."
        text = re.sub(r"…{2,}", "…", text)

    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(), log
