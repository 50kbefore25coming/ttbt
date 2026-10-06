# Văn bản → làm sạch → AI xử lý lần 2 → giọng nói (miễn phí)

Quy trình mỗi file:

```
file .txt/.md/.docx/.pdf
  → [1] Regex: xoá số chú thích (1), (2)... + chuẩn hoá "........." → "..."
  → [2] AI (Gemini miễn phí): sửa dấu câu / ký tự rác, KHÔNG được đổi lời văn
        └ chốt chặn: so sánh phần chữ bản gốc và bản AI, khác → bỏ kết quả AI
  → [3] edge-tts (miễn phí): ra file .mp3
```

## Dùng file PDF

Bỏ thẳng file `.pdf` vào `input/` rồi chạy như bình thường. Tool tự trích chữ, nối các dòng bị xuống dòng cứng, và bỏ số trang cùng tiêu đề/chân trang lặp lại (mọi thứ bị bỏ đều ghi trong `report.txt`).

- PDF dạng **ảnh scan** (không bôi đen được chữ) thì tool báo lỗi vì không có chữ để đọc. Cách xử lý: mở PDF bằng Google Docs/Google Drive để nó nhận dạng chữ rồi tải về `.docx`, hoặc dùng công cụ OCR.
- Nếu `report.txt` cảnh báo lỗi font, chữ tiếng Việt có thể sai dấu. Thử chuyển PDF sang `.docx` bằng Word hoặc Google Docs rồi đưa vào.
- Tiêu đề lặp lại chỉ được nhận ra khi PDF có từ 3 trang trở lên.
- Nếu tool nối dòng sai ý bạn, chạy lại với `--pdf-raw` để giữ nguyên chữ trích ra.
- **Luôn đọc `02_final.txt` trước khi tạo mp3**, vì PDF là định dạng hay gây lỗi nhất.

## Cài đặt (làm 1 lần)

```bash
pip install -r requirements.txt
```

1. Vào https://aistudio.google.com → **Get API key** (miễn phí, chỉ cần tài khoản Google).
2. Copy `.env.example` thành `.env`, dán key vào `GEMINI_API_KEY=...`.

## Cách dùng

```bash
# Thử trước, chỉ làm sạch bằng regex, không AI, không tạo mp3 → xem output/<tên>/report.txt
python main.py input/chuong1.docx --no-ai --no-tts

# Chạy đủ: regex + AI + hỏi trước khi đọc
python main.py input/chuong1.docx

# Cả thư mục / nhiều file, không hỏi nữa
python main.py input/ --yes
python main.py input/*.docx --yes

# Đổi giọng nam, đọc chậm hơn
python main.py input/chuong1.docx --voice vi-VN-NamMinhNeural --rate=-10%
```

Kết quả nằm trong `output/<tên file>/`:

| File | Nội dung |
|---|---|
| `01_cleaned.txt` | Sau bước regex |
| `02_final.txt` | Sau bước AI (đây là văn bản đưa vào TTS) |
| `report.txt` | Thống kê trước/sau, **từng chỗ (n) đã xoá kèm ngữ cảnh**, các đoạn AI bị loại |
| `<tên>.mp3` | Giọng đọc |

**Nên làm:** chạy 1 file với `--no-tts`, đọc `report.txt` kiểm tra, rồi mới chạy cả loạt với `--yes`.

## Viết rule cho AI ở đâu?

Có 2 file ở thư mục gốc, **không cần sửa code**:

| File | Dùng khi | Cách viết |
|---|---|---|
| `rules.txt` | Muốn AI hiểu ngữ cảnh (cảm thán, ngập ngừng, ngắt lời...) | Câu tiếng Việt thường, mỗi dòng 1 rule. Dòng bắt đầu bằng `#` bị bỏ qua |
| `replacements.txt` | Muốn thay thế **chắc chắn, không phụ thuộc AI** | `regex => thay thế`, ví dụ `--+ => ...` |

- Nếu `rules.txt` có rule đang bật, tool sẽ gửi **tất cả** đoạn cho AI (vì rule có thể áp dụng ở bất cứ đâu). Số request tăng lên, hãy xem mục hạn mức bên dưới.
- Rule của AI chỉ có tác dụng với **dấu câu và khoảng trắng**. Nếu AI đổi/thêm/bớt chữ, chốt chặn sẽ loại đoạn đó và dùng bản gốc (ghi trong `report.txt`). Muốn đổi chữ thì dùng `replacements.txt`.
- Đổi `rules.txt` thì cache tự vô hiệu, AI sẽ xử lý lại theo rule mới.
- Rule nên cụ thể, kèm ví dụ ngắn. Ví dụ tốt: `Câu chỉ có "Hả?" trong ngoặc kép thì viết thành "Hả?!"`. Ví dụ dễ sai: `Làm cho cảm xúc hơn`.
- Prompt gốc (các quy tắc tuyệt đối) nằm ở `BASE_SYSTEM` trong `src/ai_pass.py`.

## Giới hạn miễn phí và cách tiết kiệm

- Mặc định chỉ gửi AI những đoạn có dấu hiệu lạ (số chú thích sót, dấu câu lạ, ký tự rác). Muốn gửi hết: `--ai-all`.
- Có nghỉ 6 giây giữa các request (`--ai-delay`). Đoạn đã xử lý được lưu trong `.cache/`, nên chạy lại không tốn hạn mức.
- Nếu gặp lỗi 429 liên tục, tool tự tắt AI cho phần còn lại (vẫn tạo mp3 từ bản regex). Hôm sau chạy lại là tiếp tục từ cache.
- Xem hạn mức thật của tài khoản trong AI Studio, vì Google đổi số này thường xuyên.
- Gói miễn phí của Google có thể dùng nội dung bạn gửi để cải thiện sản phẩm. Đừng gửi dữ liệu nhạy cảm.

## Lưu ý về độ chính xác

- Regex xoá mọi `(số 1-3 chữ số)`. Nếu văn bản có danh sách thật kiểu "(1) làm A, (2) làm B" thì sẽ bị xoá nhầm; hãy kiểm tra `report.txt`.
- Dòng chú thích cuối trang bắt đầu bằng `(1) Giải thích...` chỉ bị xoá khi bật `--strip-footnote-lines`.
- Muốn dùng model khác: `--model gemini-2.5-flash` (hoặc chạy `python list_models.py` để xem model key của bạn dùng được).

## Cấu trúc

```
main.py            điểm chạy
src/cleaner.py     regex xoá (n), log ngữ cảnh
src/ai_pass.py     Gemini + kiểm chứng + cache (prompt gốc: BASE_SYSTEM)
src/replacements.py thay thế cố định
rules.txt          rule viết cho AI
replacements.txt   regex => thay thế
src/chunker.py     cắt đoạn theo câu
src/tts.py         edge-tts
tests/             python -m unittest discover
```
