"""Đọc PDF (có lớp chữ) và dựng lại văn bản cho đỡ "gãy".

PDF lưu chữ theo từng dòng hiển thị, nên khi trích ra thường bị:
  - câu bị ngắt giữa chừng ở cuối mỗi dòng       -> nối lại các dòng bị xuống dòng cứng
  - số trang, tiêu đề lặp lại đầu/cuối mỗi trang -> xoá (có ghi log)
PDF dạng ảnh scan (không có lớp chữ) thì không đọc được, cần OCR trước.
"""
import re
from collections import Counter

END_PUNCT = re.compile(r"[.!?…”\"’:;)\]]$")
PAGE_NUM = re.compile(r"^(?:trang|page|tr\.)?\s*\d{1,4}\s*$", re.I)


def extract_pages(path):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise ValueError("PDF bị khoá mật khẩu.")
    return [(p.extract_text() or "") for p in reader.pages]


def _header_like(line: str) -> bool:
    """Tiêu đề/chân trang thường KHÔNG phải lời thoại: không mở ngoặc kép, không kết thúc bằng dấu câu."""
    s = line.strip()
    return bool(s) and not re.match(r"[“\"‘']", s) and not re.search(r"[.!?…”\"’]$", s)


def _norm_header(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip())


def rebuild(pages, cleanup=True):
    """pages: list[str] (mỗi phần tử là chữ của 1 trang) -> (văn_bản, ghi_chú)."""
    notes = []
    n = len(pages)
    if n == 0 or sum(len(p.strip()) for p in pages) < 30 * n:
        raise ValueError(
            "PDF gần như không có chữ (có thể là bản scan/ảnh). Cần chạy OCR trước "
            "(ví dụ mở PDF bằng Google Drive/Google Docs để nó nhận dạng chữ, rồi tải về .docx).")

    bad = sum(p.count("\ufffd") + len(re.findall(r"[\ue000-\uf8ff]", p)) for p in pages)
    if bad > 20:
        notes.append(f"CẢNH BÁO: có {bad} ký tự lỗi font trong PDF; chữ tiếng Việt có thể sai dấu. "
                     "Nên thử xuất lại PDF hoặc chuyển qua .docx bằng Word/Google Docs.")

    page_lines = [[l.rstrip() for l in p.splitlines()] for p in pages]

    if cleanup:
        # Đếm các dòng ở vị trí đầu/cuối trang (2 dòng đầu + 2 dòng cuối) lặp lại nhiều trang
        counter = Counter()
        for lines in page_lines:
            ne = [l for l in lines if l.strip()]
            edge = set(_norm_header(l) for l in ne[:2] + ne[-2:] if _header_like(l))
            counter.update(edge)
        threshold = max(3, int(n * 0.3))
        repeated = {k for k, c in counter.items() if c >= threshold and len(k) <= 80}

        cleaned_pages = []
        for pi, lines in enumerate(page_lines, 1):
            ne_idx = [i for i, l in enumerate(lines) if l.strip()]
            edge_idx = set(ne_idx[:2] + ne_idx[-2:])
            keep = []
            for i, l in enumerate(lines):
                s = l.strip()
                if i in edge_idx and s:
                    if PAGE_NUM.match(s):
                        notes.append(f"[p{pi}] bỏ số trang: {s!r}")
                        continue
                    if _header_like(s) and _norm_header(s) in repeated:
                        notes.append(f"[p{pi}] bỏ tiêu đề/chân trang lặp: {s[:60]!r}")
                        continue
                keep.append(l)
            cleaned_pages.append(keep)
        page_lines = cleaned_pages

    lines = [l.strip() for ls in page_lines for l in ls]

    # Ước lượng độ dài một dòng "đầy" để nhận ra dòng bị xuống dòng cứng
    lens = sorted(len(l) for l in lines if len(l) > 20)
    p90 = lens[int(len(lens) * 0.9)] if lens else 0

    out, buf, joined = [], "", 0
    for l in lines:
        if not l:
            if buf:
                out.append(buf)
                buf = ""
            continue
        if buf:
            buf += " " + l
            joined += 1
        else:
            buf = l
        wrapped = cleanup and p90 and len(l) >= 0.85 * p90 and not END_PUNCT.search(l)
        if not wrapped:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    if cleanup:
        notes.append(f"Đã nối {joined} chỗ xuống dòng cứng (độ dài dòng đầy ≈ {p90} ký tự)")
    return "\n".join(out), notes
