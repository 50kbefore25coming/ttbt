"""Bước 2: AI (Gemini, gói miễn phí) xử lý lần 2 + chốt chặn kiểm chứng.

AI chỉ được sửa dấu câu / khoảng trắng / ký tự rác. Sau khi AI trả về, ta so sánh
"dấu vân tay" phần CHỮ của bản gốc và bản AI. Khác nhau => AI đã đổi lời văn
=> bỏ kết quả AI, dùng lại bản gốc của đoạn đó.
"""
import hashlib
import json
import os
import re
import time
import unicodedata
from pathlib import Path

BASE_SYSTEM = """Bạn là bộ tiền xử lý văn bản tiếng Việt để đưa vào máy đọc (TTS).
QUY TẮC TUYỆT ĐỐI:
- KHÔNG thêm, bớt, đổi, viết lại bất kỳ TỪ nào. Giữ nguyên từng chữ, từng dấu thanh.
- Chỉ được sửa: dấu câu, khoảng trắng, và ký tự rác.
- Giữ nguyên các câu cảm thán, dấu ?, !, dấu ngoặc kép, dấu "..." thể hiện ngập ngừng.
- Chuỗi chấm quá dài (.......) đổi thành "...".
- Nếu còn số chú thích dạng (n) hoặc [n] sót lại (không phải lời văn) thì xoá.
- Giữ nguyên xuống dòng.
- Chỉ trả về văn bản đã xử lý, không giải thích, không dùng markdown."""

def build_system(user_rules: str = "") -> str:
    user_rules = (user_rules or "").strip()
    if not user_rules:
        return BASE_SYSTEM
    return (BASE_SYSTEM
            + "\n\nQUY TẮC BỔ SUNG CỦA NGƯỜI DÙNG (chỉ áp dụng trong phạm vi dấu câu/khoảng trắng; "
              "KHÔNG ĐƯỢC vi phạm các quy tắc tuyệt đối ở trên):\n" + user_rules)


# Đoạn nào có dấu hiệu "cần AI nhìn" thì mới gọi (tiết kiệm hạn mức miễn phí).
SUSPICIOUS = re.compile(
    r"\(\s*\d+\s*\)|\[\s*\d+\s*\]"      # số chú thích sót
    r"|[!?]{2,}|(?<!\.)\.{2}(?!\.)|\.{4,}"     # dấu câu lạ
    r"|[^\w\s.,!?…“”\"'‘’():;\-–—/%]"     # ký tự rác
)


DEFAULT_MODEL = "gemini-3.1-flash-lite"
FALLBACK_MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash"]


def classify_error(e) -> str:
    """Phân loại lỗi API: daily | rate | notfound | auth | other."""
    code = getattr(e, "code", None)
    msg = str(e).lower()
    flat = msg.replace("_", "").replace(" ", "")
    if code == 429 or "resourceexhausted" in flat or "quota" in msg:
        return "daily" if "perday" in flat else "rate"
    if code == 404 or "notfound" in flat:
        return "notfound"
    if code in (400, 401, 403) or "apikey" in flat or "permission" in msg:
        return "auth"
    return "other"


def fingerprint(s: str) -> str:
    """Chỉ giữ phần chữ/số (không dấu câu, khoảng trắng, số chú thích)."""
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\(\s*\d{1,3}\s*\)|\[\s*\d{1,3}\s*\]", "", s)
    return re.sub(r"[\W_]+", "", s).lower()


def needs_ai(chunk: str) -> bool:
    return bool(SUSPICIOUS.search(chunk))


def _strip_fences(t: str) -> str:
    t = t.strip()
    t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
    t = re.sub(r"\n?```$", "", t)
    return t.strip()


class AIProcessor:
    def __init__(self, model=DEFAULT_MODEL, delay=6.0, cache_dir=".cache",
                 force_all=False, max_fail=3, user_rules=""):
        self.system = build_system(user_rules)
        self._make_client()
        self.model, self.delay, self.force_all = model, delay, force_all
        self._tried = {model}
        self.max_fail = max_fail
        self.fail_streak = 0
        self.disabled = False
        self.counts = {"bỏ qua": 0, "cache": 0, "AI": 0, "bị loại": 0, "lỗi": 0}

        Path(cache_dir).mkdir(exist_ok=True)
        self.cache_file = Path(cache_dir) / "ai_cache.json"
        self.cache = (json.loads(self.cache_file.read_text(encoding="utf-8"))
                      if self.cache_file.exists() else {})

    def _make_client(self):
        from google import genai
        from google.genai import types

        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Thiếu GEMINI_API_KEY. Xem README (bước lấy key miễn phí).")
        self._types = types
        self.client = genai.Client(api_key=key)

    def _key(self, chunk):
        # rules đổi => cache tự vô hiệu, AI sẽ xử lý lại theo rule mới
        return hashlib.md5((self.model + self.system + chunk).encode("utf-8")).hexdigest()

    def _call(self, chunk, retries=5):
        for attempt in range(retries):
            try:
                r = self.client.models.generate_content(
                    model=self.model,
                    contents=chunk,
                    config=self._types.GenerateContentConfig(
                        system_instruction=self.system, temperature=0,
                        automatic_function_calling=self._types.AutomaticFunctionCallingConfig(disable=True)),
                )
                if r.text:
                    return _strip_fences(r.text)
                print("    ! AI trả về rỗng (có thể bị bộ lọc chặn đoạn này)")
                return None
            except Exception as e:
                kind = classify_error(e)
                print(f"    ! [{kind}] {e.__class__.__name__}: {str(e)[:300]}")
                if kind == "daily":
                    self.disabled = True
                    print("    -> Đã hết hạn mức NGÀY. Tắt AI; mai chạy lại, đoạn đã xong nằm trong cache.")
                    return None
                if kind == "auth":
                    self.disabled = True
                    print("    -> API key sai/không có quyền. Kiểm tra lại GEMINI_API_KEY trong file .env.")
                    return None
                if kind == "notfound":
                    nxt = [m for m in FALLBACK_MODELS if m not in self._tried]
                    if nxt:
                        self.model = nxt[0]
                        self._tried.add(self.model)
                        print(f"    -> Model không tồn tại, thử model khác: {self.model}")
                        continue
                    self.disabled = True
                    print("    -> Không model nào dùng được. Chạy `python list_models.py` rồi dùng --model <tên>.")
                    return None
                wait = 20 * (attempt + 1) if kind == "rate" else 10 * (attempt + 1)
                print(f"    -> chờ {wait}s rồi thử lại ({attempt + 1}/{retries})...")
                time.sleep(wait)
        return None

    def process(self, chunk: str, log: list) -> str:
        if self.disabled or not (self.force_all or needs_ai(chunk)):
            self.counts["bỏ qua"] += 1
            return chunk

        k = self._key(chunk)
        if k in self.cache:
            self.counts["cache"] += 1
            return self.cache[k]

        out = self._call(chunk)
        if out is None:
            self.counts["lỗi"] += 1
            self.fail_streak += 1
            if self.fail_streak >= self.max_fail:
                self.disabled = True
                print("    ! Lỗi liên tục (có thể hết hạn mức hôm nay). Tắt AI cho phần còn lại;"
                      " chạy lại sau, các đoạn đã xong được lưu cache.")
            return chunk
        self.fail_streak = 0

        if fingerprint(out) != fingerprint(chunk):
            self.counts["bị loại"] += 1
            log.append(f"AI đổi lời văn -> dùng bản gốc\n    gốc: {chunk[:90]}...\n    AI : {out[:90]}...")
            result = chunk
        else:
            self.counts["AI"] += 1
            result = out

        self.cache[k] = result
        self.cache_file.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")
        time.sleep(self.delay)
        return result
