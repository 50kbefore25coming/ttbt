import unittest

from src.ai_pass import fingerprint, needs_ai
from src.chunker import chunk_text
from src.cleaner import clean

SAMPLE = (
    "Ngươi cứ coi như đây là sự thất thường của ta đi. (1) “Nếu coi Trung Nguyên là một "
    "bàn cờ vây rộng lớn, thì nơi lão phải đặt quân cờ là bên ngoài vòng vây.”\n"
    "“Ngươi nghĩ giá trị của Hoa Sơn đến mức đó thật sao?”\n"
    "“À không, chuyện này không nói bằng lời được”\n"
    "“..........Hả?”"
)


class CleanerTest(unittest.TestCase):
    def test_removes_marker_only(self):
        out, log = clean(SAMPLE)
        self.assertNotIn("(1)", out)
        self.assertEqual(len(log), 1)
        self.assertIn("đi. “Nếu", out)           # không dính chữ, không thừa dấu cách

    def test_keeps_prose_in_parens_and_years(self):
        t = "Hoa Sơn (Cửu Phái) thành lập (1945) và (12) người."
        out, log = clean(t)
        self.assertIn("(Cửu Phái)", out)
        self.assertIn("(1945)", out)
        self.assertNotIn("(12)", out)
        self.assertEqual(len(log), 1)

    def test_exclamations_preserved(self):
        out, _ = clean(SAMPLE)
        self.assertIn("“À không, chuyện này không nói bằng lời được”", out)
        self.assertIn("“...Hả?”", out)            # chuỗi chấm dài về "..."
        self.assertIn("Hả?", out)

    def test_attached_marker(self):
        out, _ = clean("đi.(1)“Nếu và abc(2)def")
        self.assertEqual(out, "đi. “Nếu và abc def")

    def test_footnote_lines(self):
        t = "Câu một.(1)\n(1) Giải thích: đây là chú thích.\nCâu hai."
        out, _ = clean(t, strip_footnote_lines=True)
        self.assertNotIn("Giải thích", out)
        self.assertIn("Câu hai.", out)


class ChunkerTest(unittest.TestCase):
    def test_limit_and_no_text_lost(self):
        text = "\n".join(f"Câu số {i} rất là dài dòng để thử cắt đoạn." for i in range(200))
        chunks = chunk_text(text, 500)
        self.assertTrue(all(len(c) <= 500 for c in chunks))
        self.assertEqual(fingerprint("\n".join(chunks)), fingerprint(text))


class GuardTest(unittest.TestCase):
    def test_fingerprint_ignores_punct_and_markers(self):
        self.assertEqual(fingerprint("“..........Hả?”"), fingerprint("Hả (3) ..."))
        self.assertEqual(fingerprint("À không"), fingerprint("à  KHÔNG!"))

    def test_fingerprint_catches_changed_words_and_tones(self):
        self.assertNotEqual(fingerprint("Ngươi nghĩ sao"), fingerprint("Ngươi nghi sao"))
        self.assertNotEqual(fingerprint("Hoa Sơn"), fingerprint("Hoa Sơn phái"))

    def test_needs_ai(self):
        self.assertFalse(needs_ai("Chỉ là câu bình thường, có “trích dẫn” và dấu hỏi?"))
        self.assertTrue(needs_ai("Còn sót (7) ở đây"))
        self.assertTrue(needs_ai("Hả?!?? ###"))


if __name__ == "__main__":
    unittest.main()


# ---------- Test luồng AI bằng "AI giả" (không cần mạng) ----------
import tempfile
from src.ai_pass import AIProcessor, build_system
from src.replacements import apply_replacements, load_replacements
from pathlib import Path


class FakeAI(AIProcessor):
    def _make_client(self):
        self.calls = 0
        self.reply = None          # hàm: chunk -> chuỗi | None

    def _call(self, chunk, retries=3):
        self.calls += 1
        return self.reply(chunk)


class AIFlowTest(unittest.TestCase):
    def make(self, reply, **kw):
        ai = FakeAI(delay=0, cache_dir=tempfile.mkdtemp(), **kw)
        ai.reply = reply
        return ai

    def test_good_output_accepted(self):
        ai = self.make(lambda c: c.replace("Hả?", "Hả?!"))
        log = []
        out = ai.process("“Hả?” ### rác", log)      # có ký tự rác => gọi AI
        self.assertIn("Hả?!", out)
        self.assertEqual(log, [])
        self.assertEqual(ai.counts["AI"], 1)

    def test_changed_words_rejected(self):
        ai = self.make(lambda c: c.replace("Hoa Sơn", "Hoa Sơn phái"))
        log = []
        src = "Hoa Sơn ### rác"
        self.assertEqual(ai.process(src, log), src)
        self.assertEqual(ai.counts["bị loại"], 1)
        self.assertEqual(len(log), 1)

    def test_cache_and_rules_invalidate(self):
        ai = self.make(lambda c: c)
        ai.process("a ### b", [])
        ai.process("a ### b", [])
        self.assertEqual(ai.calls, 1)               # lần 2 lấy từ cache
        self.assertIn("rule của tôi", build_system("rule của tôi"))

    def test_failure_disables_ai(self):
        ai = self.make(lambda c: None, max_fail=2)
        for i in range(3):
            ai.process(f"x{i} ### y", [])
        self.assertTrue(ai.disabled)
        self.assertEqual(ai.calls, 2)               # sau khi tắt không gọi nữa

    def test_force_all(self):
        ai = self.make(lambda c: c, force_all=True)
        ai.process("câu bình thường", [])
        self.assertEqual(ai.calls, 1)

    def test_ellipsis_alone_not_suspicious(self):
        self.assertFalse(needs_ai("Hả... thật sao?"))


class ReplacementTest(unittest.TestCase):
    def test_apply(self):
        d = tempfile.mkdtemp()
        f = Path(d) / "r.txt"
        f.write_text("# chú thích\n--+ => ...\n\\bHả\\?(?=”) => Hả?!\n", encoding="utf-8")
        out, log = apply_replacements("“Hả?” và -- xong", load_replacements(f))
        self.assertEqual(out, "“Hả?!” và ... xong")
        self.assertEqual(len(log), 2)

    def test_bad_line(self):
        d = tempfile.mkdtemp()
        f = Path(d) / "r.txt"
        f.write_text("thiếu dấu mũi tên\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_replacements(f)


# ---------- PDF ----------
from src.pdf_reader import rebuild


class PdfTest(unittest.TestCase):
    def pages(self):
        body = [
            "Ngươi cứ coi như đây là sự thất thường của ta đi nhưng thật ra không phải vậy đâu",
            "mà là có lý do khác khiến lão phải làm như thế này.",
            "“À không, chuyện này không nói bằng lời được”",
        ]
        return [f"Hoa Sơn Ký - Chương 1\n" + "\n".join(body) + f"\n{i}" for i in range(1, 5)]

    def test_header_pagenum_removed_and_lines_joined(self):
        text, notes = rebuild(self.pages())
        self.assertNotIn("Hoa Sơn Ký", text)
        self.assertNotIn("\n1\n", "\n" + text + "\n")
        self.assertIn("không phải vậy đâu mà là có lý do khác", text)   # đã nối dòng
        self.assertIn("“À không, chuyện này không nói bằng lời được”", text)
        self.assertTrue(any("tiêu đề" in n for n in notes))

    def test_raw_mode_keeps_everything(self):
        text, _ = rebuild(self.pages(), cleanup=False)
        self.assertIn("Hoa Sơn Ký", text)

    def test_scanned_pdf_rejected(self):
        with self.assertRaises(ValueError):
            rebuild(["", " ", ""])


from src.ai_pass import classify_error


class _E(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


class ErrorClassTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(classify_error(_E(429, "RESOURCE_EXHAUSTED GenerateRequestsPerMinutePerProject")), "rate")
        self.assertEqual(classify_error(_E(429, "quota GenerateRequestsPerDayPerProjectPerModel-FreeTier")), "daily")
        self.assertEqual(classify_error(_E(404, "models/xyz is not found")), "notfound")
        self.assertEqual(classify_error(_E(400, "API key not valid")), "auth")
        self.assertEqual(classify_error(_E(500, "internal")), "other")
