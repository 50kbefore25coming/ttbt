"""Đọc file đầu vào (.txt, .md, .docx, .pdf) thành văn bản.

read_document() trả về (văn_bản, ghi_chú) để đưa ghi chú vào report.txt.
"""
from pathlib import Path


def read_document(path, pdf_raw=False):
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".docx":
        from docx import Document
        doc = Document(str(p))
        return "\n".join(par.text for par in doc.paragraphs), []
    if ext in (".txt", ".md"):
        return p.read_text(encoding="utf-8-sig"), []
    if ext == ".pdf":
        from .pdf_reader import extract_pages, rebuild
        return rebuild(extract_pages(p), cleanup=not pdf_raw)
    raise ValueError(f"Định dạng chưa hỗ trợ: {ext} (dùng .txt, .md, .docx hoặc .pdf)")


def read_text(path) -> str:
    return read_document(path)[0]
