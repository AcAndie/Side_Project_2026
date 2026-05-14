# 🌳 TriLex

**Modern QuickTranslator với AI polish** — dịch tiểu thuyết ZH/EN/VN bằng 1.14M-entry QT dictionary + Gemini AI, output thẳng vào Obsidian vault.

---

## Tại sao TriLex khác tool khác?

Hầu hết AI translator gọi thẳng LLM → AI hallucinate tên nhân vật, drift terminology, tốn tokens.

TriLex dùng **kiến trúc QT**: apply dictionary trước (deterministic, free, instant), rồi mới dùng AI để *polish* — không phải translate từ đầu.

```
ZH text → QT Dictionary Pass (free, <100ms) → Convert (Hán-Việt)
                                                      ↓
                                            LLM Polish (AI, smooth VN)
                                                      ↓
                                            Obsidian Vault (.md)
```

**Kết quả**: tên nhân vật không bao giờ drift, token ít hơn 40–60%, hoạt động ngay cả khi hết API quota.

---

## Features

| Feature | Mô tả |
|---|---|
| **4 translation routes** | ZH→VN, ZH→EN, EN→VN, VN→EN |
| **3 modes** | Convert (no AI), Polish (AI), Side-by-side |
| **QT Dictionary Engine** | VietPhrase.txt + Names.txt + LuatNhan.txt, Aho-Corasick automaton |
| **Name Lock** | 3-layer enforcement: pre-translate → prompt → post-validate |
| **AI Polish** | Gemini 2.5 Flash default; Claude/DeepSeek optional |
| **Glossary per novel** | Lock term → tên nhân vật dịch nhất quán toàn bộ |
| **Obsidian vault output** | Mỗi chương = 1 `.md` file, có frontmatter |
| **EPUB export** | Đóng gói toàn bộ novel thành `.epub` |
| **Resume pipeline** | Đóng laptop giữa chừng → mở lên dịch tiếp |
| **Auto problem detection** | Phát hiện chữ Hán sót, tên sai, đoạn bị skip |
| **Streamlit UI** | Web UI local, không cần host |
| **CLI** | `trilex translate`, `trilex db init`, ... |

---

## Quick Start — 5 bước

### Bước 1: Cài Python & uv

```bash
# Cài uv (package manager nhanh hơn pip 10x)
# Windows PowerShell:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Bước 2: Clone và cài dependencies

```bash
git clone <repo-url>
cd trilex
uv sync
```

### Bước 3: Thêm QT dictionaries

```
trilex/
└── data/
    └── dictionaries/
        ├── VietPhrase.txt    ← bắt buộc
        ├── Names.txt         ← nên có
        └── LuatNhan.txt      ← tùy chọn
```

> **Tải dictionaries**: VietPhrase.txt và Names.txt có thể tìm thấy trong các bản phát hành cũ của QuickTranslator (GitHub: vietphrase community).

### Bước 4: Tạo file `.env`

```bash
cp .env.example .env
# Sửa .env, điền GEMINI_API_KEY
```

```env
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
```

### Bước 5: Khởi động và dịch

```bash
# Init database
uv run trilex db init

# Mở UI
uv run streamlit run src/trilex/ui/app.py
```

Truy cập `http://localhost:8501` → **Library** → tạo project → **Translate** → paste chương ZH → Click **Translate Now**.

---

## Screenshots

> *(Sẽ cập nhật sau)*

| Library | Translate | Glossary |
|---|---|---|
| ![Library](docs/screenshots/library.png) | ![Translate](docs/screenshots/translate.png) | ![Glossary](docs/screenshots/glossary.png) |

---

## Tech Stack

| Layer | Tech |
|---|---|
| Language | Python 3.11+ |
| Package manager | uv |
| Database | SQLite + SQLAlchemy 2.0 + Alembic |
| Validation | Pydantic v2 |
| String matching | pyahocorasick (Aho-Corasick automaton) |
| LLM | Gemini 2.5 Flash (default), Claude, DeepSeek |
| UI | Streamlit |
| CLI | Typer |
| Output | Obsidian Markdown + EPUB |

---

## Cấu trúc folder

```
trilex/
├── src/trilex/          # Source code
│   ├── core/            # Pure logic (models, pipeline, transforms)
│   ├── qt_dict/         # QT dictionary engine
│   ├── providers/       # LLM adapters
│   ├── persistence/     # SQLite + repos
│   ├── output/          # Obsidian, EPUB, plain text writers
│   ├── memory/          # Scout + narrative memory
│   ├── ui/              # Streamlit pages
│   └── cli/             # CLI commands
├── data/                # User data (gitignored)
│   ├── dictionaries/    # VietPhrase.txt, Names.txt, ...
│   ├── vault/           # Obsidian vault output
│   └── trilex.db        # SQLite database
├── packs/               # Style packs per genre (tu_tien, litrpg, ...)
└── tests/               # pytest unit + integration tests
```

---

## License

MIT © AcAndie
