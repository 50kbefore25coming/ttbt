"""Công cụ: văn bản -> làm sạch (xoá (n)) -> AI xử lý lần 2 -> giọng nói (mp3).

Ví dụ:
  python main.py input/chuong1.docx
  python main.py input/                      (cả thư mục)
  python main.py input/*.pdf --yes
  python main.py input/chuong1.txt --no-ai --no-tts     (chỉ làm sạch để kiểm tra)
  python main.py input/chuong1.docx --rate=-10%         (đọc chậm hơn; nhớ dùng dấu =)
"""
import argparse
import glob
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):          # tránh lỗi tiếng Việt trên console Windows
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.reader import read_document
from src.cleaner import clean
from src.chunker import chunk_text
from src.replacements import load_replacements, apply_replacements
from src.stats import stats, fmt

EXTS = {".txt", ".md", ".docx", ".pdf"}


def load_user_rules(path) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    lines = [l.strip() for l in p.read_text(encoding="utf-8-sig").splitlines()]
    return "\n".join(l for l in lines if l and not l.startswith("#"))


def collect_inputs(args):
    files = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            files += sorted(x for x in p.iterdir()
                            if x.suffix.lower() in EXTS and not x.name.startswith("~$"))
        else:
            matched = sorted(glob.glob(a)) or [a]   # Windows không tự mở rộng dấu *
            files += [Path(m) for m in matched]
    return files


def process_file(path: Path, args, ai, repl_rules):
    print(f"\n=== {path.name} ===")
    out_dir = Path(args.outdir) / path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    raw, read_notes = read_document(path, pdf_raw=args.pdf_raw)
    before = stats(raw)

    # Bước 1: regex xoá (n) + thay thế cố định
    cleaned, log = clean(raw, strip_footnote_lines=args.strip_footnote_lines)
    cleaned, repl_log = apply_replacements(cleaned, repl_rules)
    (out_dir / "01_cleaned.txt").write_text(cleaned, encoding="utf-8")

    # Bước 2: AI
    ai_log = []
    if ai:
        parts = chunk_text(cleaned, args.ai_chunk)
        mode = "TẤT CẢ đoạn" if ai.force_all else "chỉ đoạn có dấu hiệu lạ"
        print(f"  AI: {len(parts)} đoạn ({mode})")
        final = "\n".join(ai.process(c, ai_log) for c in parts)
    else:
        final = cleaned
    (out_dir / "02_final.txt").write_text(final, encoding="utf-8")

    after = stats(final)
    report = [
        f"File: {path.name}",
        f"Trước: {fmt(before)}",
        f"Sau  : {fmt(after)}",
        *([f"\nĐọc file ({len(read_notes)} ghi chú):", *[f"  {l}" for l in read_notes]] if read_notes else []),
        f"\nĐã xoá {len(log)} chỗ chú thích:",
        *[f"  {l}" for l in log],
        f"\nThay thế cố định: {len(repl_log)} quy tắc có tác dụng",
        *[f"  {l}" for l in repl_log],
        f"\nAI bị loại (đổi lời văn): {len(ai_log)}",
        *[f"  {l}" for l in ai_log],
    ]
    if ai:
        report.append(f"\nThống kê AI: {ai.counts}")
    (out_dir / "report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"  Trước: {fmt(before)}\n  Sau  : {fmt(after)}")
    print(f"  Đã xoá {len(log)} chú thích | AI bị loại: {len(ai_log)}")
    print(f"  Xem lại: {out_dir / 'report.txt'}")

    # Bước 3: TTS
    if args.no_tts:
        return
    if not args.yes:
        if input("  Đọc file này thành mp3? (y/n): ").strip().lower() != "y":
            print("  Bỏ qua TTS.")
            return
    from src.tts import synthesize
    mp3 = out_dir / f"{path.stem}.mp3"
    synthesize(chunk_text(final, args.tts_chunk), mp3, args.voice, args.rate, args.pitch)
    print(f"  Xong: {mp3}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="file (.txt/.md/.docx/.pdf), thư mục hoặc mẫu *.pdf")
    ap.add_argument("--outdir", default="output")
    ap.add_argument("--voice", default="vi-VN-HoaiMyNeural",
                    help="vi-VN-HoaiMyNeural (nữ) hoặc vi-VN-NamMinhNeural (nam)")
    ap.add_argument("--rate", default="+0%", help='tốc độ đọc, ví dụ --rate=-10%% hoặc --rate=+15%%')
    ap.add_argument("--pitch", default="+0Hz")
    ap.add_argument("--no-ai", action="store_true", help="bỏ bước AI (chỉ regex)")
    ap.add_argument("--ai-all", action="store_true", help="gửi MỌI đoạn cho AI (tốn hạn mức)")
    ap.add_argument("--no-tts", action="store_true", help="chỉ làm sạch, không tạo mp3")
    ap.add_argument("--strip-footnote-lines", action="store_true",
                    help='xoá cả dòng chú thích cuối trang bắt đầu bằng "(n) ..."')
    ap.add_argument("--pdf-raw", action="store_true",
                    help="PDF: giữ nguyên chữ trích ra, không nối dòng / xoá số trang")
    ap.add_argument("--model", default="gemini-3.1-flash-lite")
    ap.add_argument("--rules", default=str(ROOT / "rules.txt"), help="file rule viết cho AI")
    ap.add_argument("--replacements", default=str(ROOT / "replacements.txt"),
                    help="file thay thế cố định (regex => thay thế)")
    ap.add_argument("--ai-chunk", type=int, default=3000)
    ap.add_argument("--tts-chunk", type=int, default=2500)
    ap.add_argument("--ai-delay", type=float, default=6.0, help="giây nghỉ giữa các request AI")
    ap.add_argument("--yes", action="store_true", help="không hỏi xác nhận trước khi đọc")
    args = ap.parse_args()

    files = collect_inputs(args.inputs)
    if not files:
        sys.exit("Không tìm thấy file đầu vào.")

    repl_rules = load_replacements(args.replacements)
    user_rules = load_user_rules(args.rules)
    if repl_rules:
        print(f"Đã nạp {len(repl_rules)} quy tắc thay thế từ {Path(args.replacements).name}")

    ai = None
    if not args.no_ai:
        from src.ai_pass import AIProcessor
        if user_rules:
            print(f"Đã nạp {len(user_rules.splitlines())} rule cho AI từ {Path(args.rules).name}"
                  " -> sẽ gửi TẤT CẢ đoạn cho AI để áp dụng rule")
        try:
            ai = AIProcessor(model=args.model, delay=args.ai_delay,
                             force_all=args.ai_all or bool(user_rules), user_rules=user_rules)
        except RuntimeError as e:
            sys.exit(f"{e}\n(Muốn chạy không cần AI: thêm --no-ai)")

    for f in files:
        try:
            process_file(f, args, ai, repl_rules)
        except Exception as e:
            print(f"  !! Lỗi với {f.name}: {e}")

    print("\nHoàn tất.")


if __name__ == "__main__":
    main()
