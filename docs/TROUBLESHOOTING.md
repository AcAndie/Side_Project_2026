# TriLex — Troubleshooting

---

## Mục lục

- [Lỗi cài đặt](#lỗi-cài-đặt)
- [Lỗi API key](#lỗi-api-key)
- [Lỗi database](#lỗi-database)
- [Lỗi QT dictionary](#lỗi-qt-dictionary)
- [Lỗi dịch (pipeline)](#lỗi-dịch-pipeline)
- [Lỗi UI / Streamlit](#lỗi-ui--streamlit)
- [Lỗi export](#lỗi-export)

---

## Lỗi cài đặt

### `uv: command not found`

**Vấn đề**: uv chưa được cài hoặc chưa có trong PATH.

**Fix**:
1. Cài uv:
   - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Mở terminal mới (để PATH reload)
3. Kiểm tra: `uv --version`

---

### `trilex: command not found` sau khi `uv sync`

**Vấn đề**: package chưa được install vào venv.

**Fix**:
```bash
uv sync
uv run trilex --help   # dùng uv run thay vì gọi trực tiếp
```

Hoặc activate venv:
```bash
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

---

### `ModuleNotFoundError: No module named 'trilex'`

**Vấn đề**: chạy `python` trực tiếp thay vì `uv run`.

**Fix**: luôn dùng `uv run python` hoặc `uv run trilex`. Hoặc activate venv trước.

---

## Lỗi API key

### `ValidationError: GEMINI_API_KEY must not be empty`

**Vấn đề**: file `.env` chưa có hoặc `GEMINI_API_KEY` bị bỏ trống.

**Fix**:
1. Tạo `.env` từ template: `cp .env.example .env`
2. Mở `.env`, điền key thật vào `GEMINI_API_KEY=AIza...`
3. Đảm bảo không có space thừa quanh `=`

---

### `google.api_core.exceptions.PermissionDenied: API key not valid`

**Vấn đề**: key sai hoặc hết hạn.

**Fix**:
1. Vào [Google AI Studio](https://aistudio.google.com/apikey)
2. Copy key mới
3. Update `.env`

---

### `google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded`

**Vấn đề**: hết free quota của Gemini key chính.

**Fix** (chọn 1):
1. **Dùng fallback keys**: thêm `FALLBACK_KEY_1=AIza...` vào `.env` — TriLex tự retry với key tiếp theo
2. **Dùng Convert mode**: QT pass không cần API
3. **Đợi quota reset**: Google reset quota hàng ngày lúc 00:00 UTC

---

### API trả về content bị từ chối (Gemini Safety Filter)

**Vấn đề**: Gemini từ chối dịch nội dung tu tiên/võ thuật vì safety filter.

**Fix**: TriLex đã disable safety filters theo mặc định trong [src/trilex/providers/gemini.py](../src/trilex/providers/gemini.py). Nếu vẫn bị từ chối, kiểm tra xem file provider có đúng không:

```python
safety_settings = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    # ...
}
```

---

## Lỗi database

### `sqlite3.OperationalError: no such table: projects`

**Vấn đề**: database chưa được khởi tạo.

**Fix**:
```bash
uv run trilex db init
```

---

### `alembic.util.exc.CommandError: Can't locate revision`

**Vấn đề**: database schema outdated sau khi update code.

**Fix**:
```bash
# Backup trước
cp data/trilex.db data/trilex.db.backup

# Chạy migration
uv run trilex db migrate
```

---

### `IntegrityError: UNIQUE constraint failed: chapters.project_id, chapters.chapter_index`

**Vấn đề**: đang cố insert chapter với cùng index vào cùng project.

**Fix**: pipeline tự xử lý trường hợp này (upsert). Nếu gặp lỗi này ngoài pipeline, kiểm tra code đang dùng `chapter_repo.upsert()` thay vì `chapter_repo.create()`.

---

### UI hiện `"Cơ sở dữ liệu chưa khởi tạo"`

**Fix**:
```bash
uv run trilex db init
# Sau đó refresh trang Streamlit
```

---

## Lỗi QT dictionary

### `QTParseError: Failed to parse dict file`

**Vấn đề**: file dictionary bị corrupt hoặc encoding sai.

**Fix**:
1. Kiểm tra encoding: file phải là UTF-8
2. Mở file bằng Notepad++ → encoding → chọn "Convert to UTF-8"
3. Lưu lại và thử lại

---

### QT pass không apply — tên nhân vật vẫn là chữ Hán

**Vấn đề** có thể do:
- Không có file `VietPhrase.txt` trong `data/dictionaries/`
- File dictionary không chứa entry cho tên đó
- Source lang không phải ZH (QT pass chỉ chạy khi source = ZH)

**Fix**:
1. Kiểm tra file tồn tại: `ls data/dictionaries/`
2. UI → **Dictionary** → kiểm tra số entries loaded
3. Thêm term thủ công vào glossary project

---

### `FileNotFoundError: data/dictionaries/ does not exist`

**Fix**:
```bash
mkdir -p data/dictionaries
# Đặt VietPhrase.txt và Names.txt vào đây
```

---

### Automaton build mất quá lâu

**Bình thường**: lần đầu build automaton từ 1.14M entries mất 10–30 giây.

Nếu mỗi lần chạy đều mất lâu: cache bị hỏng.

**Fix**:
```bash
# Xóa cache và rebuild
rm -rf data/cache/
uv run trilex dict rebuild-cache
```

---

## Lỗi dịch (pipeline)

### Chapter state = `"failed"`, warning = `"preprocess.empty_input"`

**Vấn đề**: chapter paste vào rỗng hoặc chỉ có khoảng trắng.

**Fix**: kiểm tra nội dung text area trước khi submit.

---

### Output thiếu đoạn / bị cắt giữa chừng

**Vấn đề**: chapter quá dài (>4000 tokens), Gemini cắt output.

**Giải pháp hiện tại**: chia chapter thành 2 phần, dịch riêng từng phần.

> Chunking tự động đang trong roadmap — xem `BUGS_FOUND.md KI-1`.

---

### Tên nhân vật bị dịch sai trong output

**Vấn đề**: LLM override glossary.

**Fix**:
1. Thêm term vào **Glossary** → bật **Lock**
2. Retranslate chapter

TriLex có post-validation step tự động sửa tên sai — nếu vẫn sai sau đó, vui lòng mở issue.

---

### `TimeoutError` khi gọi Gemini

**Vấn đề**: response quá lâu (> 60 giây mặc định).

**Fix**: thêm vào `.env`:
```env
REQUEST_TIMEOUT=120
```

---

### Job bị stuck ở `"running"` sau khi tắt UI

**Vấn đề**: UI bị đóng trong khi job đang chạy. Job không có cơ chế tự rollback.

**Fix**:
```bash
uv run trilex job reset --job-id <id>
# Hoặc reset tất cả jobs stuck
uv run trilex job reset --all-stuck
```

---

## Lỗi UI / Streamlit

### Streamlit không start — `Address already in use`

**Vấn đề**: đang có instance Streamlit khác chạy.

**Fix**:
```bash
# Windows
netstat -ano | findstr :8501
taskkill /PID <pid> /F

# macOS/Linux
lsof -ti:8501 | xargs kill
```

Hoặc chạy trên port khác:
```bash
uv run streamlit run src/trilex/ui/app.py --server.port 8502
```

---

### Trang Streamlit bị trắng / không load

**Fix**:
1. Hard refresh: `Ctrl + Shift + R`
2. Clear Streamlit cache: UI → top-right menu → **Clear cache**
3. Restart Streamlit

---

### `StreamlitAPIException: Session state not initialized`

**Vấn đề**: truy cập `st.session_state` key chưa được set.

**Fix**: đây là bug — vui lòng mở issue với screenshot và bước tái hiện.

---

## Lỗi export

### EPUB tạo ra bị lỗi không mở được

**Vấn đề**: có thể do tên chapter hoặc title chứa ký tự đặc biệt.

**Fix**: đổi project title tránh dùng ký tự `< > : " / \ | ? *`

---

### Export chỉ ra file rỗng

**Vấn đề**: không có chapter nào trong project hoặc tất cả chapters ở trạng thái `failed`.

**Fix**: kiểm tra Jobs tab — đảm bảo ít nhất một chapter có `state = "done"`.

---

## Vẫn không fix được?

1. Chạy `uv run trilex doctor` để kiểm tra toàn bộ setup
2. Đọc log file tại `data/logs/trilex.log`
3. Mở issue tại GitHub với:
   - Mô tả lỗi
   - Error message đầy đủ
   - OS + Python version (`python --version`)
   - Output của `uv run trilex --version`
