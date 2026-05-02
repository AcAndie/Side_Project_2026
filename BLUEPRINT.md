# TriLex — Project Blueprint v1.0

> **Một công cụ dịch tiểu thuyết cá nhân** kết hợp QT dictionaries (QuickTranslator format) + AI polish, output thân thiện với cả Obsidian (đọc) và copy-paste lên web (đăng).
>
> Tên dự án là tạm thời. Đổi gì cũng được (đề xuất: TriLex, Mạch Dịch, Hán Việt AI, Lưu Vân, ...).

---

## 1. Vision

Build a **single-user, offline-first translation tool** that:
- Accepts ZH / VN / EN as source, outputs VN / EN as target (4 active routes)
- Uses **QuickTranslator-format dictionaries** (~1.14M entries from QT/VietPhrase ecosystem) as primary knowledge layer
- Uses LLM (Gemini default, Claude/DeepSeek optional) only for **polishing**, not raw translation
- Outputs both Obsidian-friendly markdown AND clipboard-ready plain text
- Supports name lock, glossary versioning, narrative memory across chapters

**Inspiration**: LiTTrans v5.7 (architecture), JP→VN system prompt (style sophistication), QuickTranslator + VietPhrase dictionaries (translation heritage), truyendichai/Chivi (UX of "paste API key, translate").

> **Naming clarification**:
> - **QuickTranslator (QT)** is the legendary desktop engine (~2010, .NET) created by the Vietnamese convert-novel community
> - **VietPhrase** is the *dictionary* (the data) that QT loads — the name "VietPhrase" comes from the main dictionary file `VietPhrase.txt`
> - The community uses both names interchangeably, but technically: **QT = engine, VietPhrase = data**
> - TriLex re-implements QT's engine logic in modern Python, consuming the same dictionary file format

---

## 2. The QuickTranslator Insight (Why This Architecture Wins)

Most AI translators do this:
```
ZH text → LLM → VN text
```
Result: AI hallucinates names, drifts terminology, expensive (1 chương ≈ 3000-5000 tokens).

**TriLex does this** (the QT pattern, with AI added):
```
ZH text 
  → Apply QT dictionaries (deterministic, free, instant) — "the QT pass"
  → "Convert" output (raw Hán-Việt, đọc được nhưng vụng — đây chính là output gốc của QT)
  → LLM polish (with glossary + context)
  → Polished VN
```
Result:
- **Names locked at dictionary level** (impossible to drift — QT's strength)
- **Tokens cut by 40-60%** (LLM only polishes, not translates)
- **Free fallback**: convert mode works without AI when out of quota (this IS QT)
- **Consistency for free**: 1.14M-entry QT dictionary already standardized by 15+ years of community curation

This is essentially what **truyendichai/Chivi/Wikidich** do internally. Their "memory" = QT dictionary layer + LLM polish.

---

## 3. Output Strategy: Dual Mode (NEW vs LiTTrans)

```
┌────────────────────────────────────────────────────────────┐
│ MODE A — CONVERT (free, instant, no AI)                    │
│   Input: ZH chapter                                         │
│   Output: Raw Hán-Việt (như Wikidich, sstruyen)            │
│   Use: Quick read, fallback when API down                  │
│   Routes supported: ZH→VN only                              │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ MODE B — POLISH (AI-enhanced, costs tokens)                │
│   Input: ZH chapter                                         │
│   Stage 1: Auto-convert (Layer 1)                          │
│   Stage 2: LLM polishes convert + raw context              │
│   Output: Smooth VN translation                            │
│   Use: Final reading / publishing                          │
│   Routes supported: ZH→VN, ZH→EN, EN→VN, VN→EN             │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ MODE C — SIDE-BY-SIDE (export for review)                  │
│   Output: 3-column markdown (Source | Convert | Polished)  │
│   Use: Quality check, manual editing                       │
└────────────────────────────────────────────────────────────┘
```

**For copy-paste to web** (tangthuvien, sstruyen, wikidich):
- Plain text mode: chapter as one continuous text block, no markdown formatting
- "Copy" button per chapter in UI
- Optional BBCode wrapping for forums that need it

---

## 4. System Architecture

```
┌──────────────────────────────────────────────────────────┐
│  USER FACING                                              │
│  ┌────────────────────┐  ┌──────────────────────────┐    │
│  │  Streamlit UI       │  │  Obsidian Vault          │    │
│  │  (operations:       │  │  (reading + editing:     │    │
│  │   translate, jobs,  │  │   chapters, glossary,    │    │
│  │   settings, dict    │  │   characters, bible,     │    │
│  │   management)       │  │   plot canvas)           │    │
│  └────────────────────┘  └──────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
                ↓                          ↑
                ↓ writes .md               ↑ reads .md (live)
                ↓                          ↑
┌──────────────────────────────────────────────────────────┐
│  CORE PIPELINE (Python, async)                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │  ① Ingest (URL / EPUB / paste / file drop)         │  │
│  │  ② Detect lang + genre                              │  │
│  │  ③ Apply QT Dictionary Layer (if ZH source)            │  │
│  │  ④ Build context (glossary + recent chapters)       │  │
│  │  ⑤ LLM call (Gemini/Claude/DeepSeek/local)          │  │
│  │  ⑥ Post-process (clean punctuation, validate names) │  │
│  │  ⑦ Write to vault + database                        │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
                ↕                          ↕
┌──────────────────────────────────────────────────────────┐
│  PERSISTENCE                                              │
│  ┌──────────────────┐  ┌─────────────────────────────┐    │
│  │  SQLite           │  │  Obsidian Vault              │    │
│  │  • Projects       │  │  • chapters/*.md             │    │
│  │  • Glossary       │  │  • characters/*.md           │    │
│  │  • Job queue      │  │  • bible/*.md                │    │
│  │  • Audit logs     │  │  • _system/*.md (dataview)   │    │
│  │  • State          │  │                              │    │
│  └──────────────────┘  └─────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Dictionary Storage (read-only at runtime)        │    │
│  │  • VietPhrase.txt (878k)                          │    │
│  │  • Names.txt (158k)                               │    │
│  │  • LacViet.txt (66k)                              │    │
│  │  • PhienAm.txt (12k)                              │    │
│  │  • LuatNhan.txt (24k pattern rules)               │    │
│  │  → Loaded into Aho-Corasick automaton in memory   │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

---

## 5. Pipeline Detail (Per Chapter)

### Route: ZH → VN (the flagship route)

```
INPUT: Chinese chapter text
   │
   ▼
[Stage 1: Pre-process]
   • Normalize encoding, simplify punctuation
   • Strip ads, footer junk (regex)
   │
   ▼
[Stage 2: Apply QT Dictionary Layer (no AI)]
   This is the classic QuickTranslator pass.
   Priority order (highest first, longest-match within each tier):
   2.1  Custom novel-specific glossary (locked terms — overrides everything)
   2.2  LuatNhan.txt patterns (parameterized rules: 不比{0}强 → không mạnh bằng {0})
   2.3  Names.txt + Names2.txt (proper nouns → locked)
   2.4  VietPhrase.txt (878k compound words, longest-match)
   2.5  LacViet.txt (66k supplementary)
   2.6  ChinesePhienAmWords.txt (12k single chars → Hán-Việt fallback)
   2.7  Babylon.txt (Trung-Anh, used only for ZH→EN route)
   │
   ▼
[Stage 3: Branch on mode]
   ├─ MODE A (CONVERT): Output raw → write file → DONE
   └─ MODE B (POLISH): continue ↓
   │
   ▼
[Stage 4: Pre-call (LLM)]
   • Extract entity candidates from convert (potential new names)
   • Detect cảnh giới mentions, kỹ năng, pháp bảo
   • Output: Chapter Map JSON
   │
   ▼
[Stage 5: Trans-call (LLM main)]
   Prompt = [
     System: style guide for genre + target lang
     Glossary slice (only terms in this chapter)
     Recent context (3-5 chapter summaries)
     Original ZH (for nuance reference)
     CONVERT output (the bulk of text)
     INSTRUCTION: "Polish this convert into natural VN, 
                   keep all locked names, fix grammar, 
                   improve sentence flow."
   ]
   │
   ▼
[Stage 6: Post-process (no AI)]
   • Fix Vietnamese punctuation (em-dash, ellipsis)
   • Validate name lock (regex check vs glossary)
   • Strip AI preambles ("Đây là bản dịch...")
   • Normalize quote styles
   │
   ▼
[Stage 7: Post-call (LLM audit, optional)]
   • Score quality (1-5)
   • Detect drift, missing translations
   • Flag for manual review if score < 3
   • Auto-retry once if confident fix possible
   │
   ▼
[Stage 8: Persist]
   • Write to chapters/{idx}.md (Obsidian-friendly frontmatter)
   • Update SQLite glossary (new terms found)
   • Update arc memory
   • Trigger Scout if N chapters done
```

### Route: EN → VN (port from LiTTrans, no QT layer — English needs full LLM translation)
```
EN → Pre-call → Trans-call (full translation, not polish) 
   → Post-process → Post-call → Persist
```

### Route: ZH → EN (no Hán-Việt shortcut)
```
ZH → Pre-call (extract names with pinyin)
   → Trans-call (direct ZH→EN)
   → Post-process (English-specific)
   → Persist
```

### Route: VN → EN
```
VN → Pre-call (extract VN names + check if Hán-Việt origin)
   → Trans-call (direct VN→EN, with romanization hints)
   → Post-process
   → Persist
```

---

## 6. Data Sources (What to Download)

### QuickTranslator dictionary ecosystem (PRIMARY)

These are the **standard QT dictionary files**, format established by the QuickTranslator desktop app and adopted by every Vietnamese convert tool since (TTV Translate, sangtacviet, wikidich, the VietPhrase Chrome extension, etc.):

- **VietPhrase.txt** (878k entries) — main compound word dictionary (the namesake file)
- **Names.txt + Names2.txt** (158k entries) — proper nouns, characters, places
- **LacViet.txt** (66k entries) — Lạc Việt commercial dictionary
- **ChinesePhienAmWords.txt** (12k entries) — Hán-Việt mapping for individual hanzi
- **LuatNhan.txt** (24k entries) — parameterized pattern rules
- **Pronouns.txt** — pronoun overrides
- **Babylon.txt** — Chinese-English (for ZH→EN route)
- **Blacklist.txt** — strings to remove (ad text, scraping junk)

Where to get them:
- TTV community downloads (tangthuvien.vn forums)
- sangtacviet.app (live dictionaries, exportable)
- VietPhrase Chrome extension (bundles full set, ~1-click install)
- Personal collection from years of use (yours)

> **Important**: TriLex must read these files **as-is**, no format conversion. The QT format is the de-facto standard. Users dropping dictionary files into TriLex should "just work" exactly like dropping them into QT.

### Reference dictionaries (for QC)
- **Hán Nôm Dictionary** (393k entries from thivien.net) — academic accuracy
- **CC-CEDICT** (~120k) — for ZH→EN route
- **Unihan Database** (Unicode official) — character-level fallback

### Genre-specific terminology (curate yourself)
- Cultivation realms list (9-tier xianxia: Luyện Khí → Đại Thừa → Độ Kiếp)
- Common sect/clan suffixes (Tông, Phái, Môn, Các, Lâu)
- Pháp bảo categories
- LitRPG token formats ([Skill], [Stat], [+50 EXP])

---

## 7. File Structure

```
trilex/
│
├── pyproject.toml              # Modern Python project (uv/poetry)
├── .env.example
├── README.md
├── CHANGELOG.md
│
├── src/trilex/
│   ├── __init__.py
│   │
│   ├── core/                   # Pure logic, zero I/O, fully testable
│   │   ├── models/
│   │   │   ├── project.py      # Project, ProjectConfig
│   │   │   ├── chapter.py      # Chapter, ChapterState
│   │   │   ├── term.py         # Term, GlossaryEntry
│   │   │   ├── character.py
│   │   │   └── job.py          # Job, JobStatus
│   │   ├── routing/
│   │   │   ├── direction.py    # Detect & validate route
│   │   │   └── genre.py        # Detect tu_tien/litrpg/...
│   │   ├── pipeline/
│   │   │   ├── orchestrator.py
│   │   │   └── stages/
│   │   │       ├── ingest.py
│   │   │       ├── qt_pass.py        # Layer 1 application (the QT engine)
│   │   │       ├── pre_call.py
│   │   │       ├── trans_call.py
│   │   │       ├── post_text.py      # 14-pass cleanup (port from LiTTrans)
│   │   │       └── post_call.py
│   │   └── transforms/         # Pure text transformations
│   │
│   ├── qt_dict/                # QuickTranslator dictionary engine (NEW MODULE)
│   │   ├── parser.py           # Parse QT .txt format (VietPhrase, Names, LuatNhan, ...)
│   │   ├── automaton.py        # Aho-Corasick for fast longest-match
│   │   ├── applier.py          # Apply with priority order (the "QT pass")
│   │   ├── luat_nhan.py        # Pattern rule engine (不比{0}强 templates)
│   │   ├── pronoun.py          # Pronoun override layer
│   │   ├── blacklist.py        # Strip junk before translation
│   │   └── importers/          # Bulk import from QT dict bundles
│   │
│   ├── providers/              # LLM adapters
│   │   ├── base.py             # Abstract LLMProvider
│   │   ├── gemini.py
│   │   ├── claude.py
│   │   ├── deepseek.py         # Cheap alternative for ZH
│   │   ├── openai_compat.py    # OpenRouter / Ollama / LM Studio
│   │   └── pool.py             # Key rotation + fallback
│   │
│   ├── ingest/                 # Input adapters
│   │   ├── scrapers/
│   │   │   ├── base.py
│   │   │   ├── qidian.py       # Chinese sites
│   │   │   ├── 69shu.py
│   │   │   ├── sfacg.py
│   │   │   ├── royalroad.py    # English (already in LiTTrans)
│   │   │   └── generic.py      # AI-learned profile (port from LiTTrans)
│   │   ├── epub.py
│   │   ├── paste.py            # Direct text paste
│   │   └── file_drop.py        # .txt/.md drop
│   │
│   ├── output/                 # Output adapters
│   │   ├── obsidian.py         # Write Obsidian-formatted .md
│   │   ├── plain_text.py       # Clipboard-friendly
│   │   ├── bbcode.py           # For forums
│   │   ├── epub.py             # EPUB export
│   │   └── side_by_side.py     # 3-column comparison
│   │
│   ├── persistence/
│   │   ├── db.py               # SQLAlchemy/SQLModel + connection
│   │   ├── migrations/         # Alembic
│   │   ├── repos/
│   │   │   ├── project_repo.py
│   │   │   ├── glossary_repo.py
│   │   │   ├── chapter_repo.py
│   │   │   └── job_repo.py
│   │   └── vault.py            # Obsidian vault file ops
│   │
│   ├── memory/                 # Layer 3 (narrative context)
│   │   ├── arc_memory.py       # Chapter summaries
│   │   ├── scout.py            # Forward-reading agent
│   │   └── bible.py            # 3-tier knowledge base
│   │
│   ├── ui/                     # Streamlit (operations only)
│   │   ├── app.py
│   │   ├── pages/
│   │   │   ├── library.py
│   │   │   ├── translate.py
│   │   │   ├── jobs.py         # Active translation jobs monitor
│   │   │   ├── dictionary.py   # QT dict management (load, view, edit)
│   │   │   ├── glossary.py     # Per-novel glossary
│   │   │   ├── settings.py
│   │   │   └── export.py
│   │   └── runners/            # Background job threading
│   │
│   └── cli/                    # Optional Typer CLI
│       └── commands.py
│
├── data/                       # User data (gitignored)
│   ├── dictionaries/           # QT dictionary .txt files (drop in as-is)
│   │   ├── VietPhrase.txt
│   │   ├── Names.txt
│   │   ├── Names2.txt
│   │   ├── ChinesePhienAmWords.txt
│   │   ├── LuatNhan.txt
│   │   ├── Pronouns.txt
│   │   └── ...
│   ├── trilex.db               # SQLite
│   └── vault/                  # Obsidian vault
│       └── projects/
│
├── packs/                      # Style packs (versioned in git)
│   ├── style/
│   │   ├── tu_tien.vn.yaml
│   │   ├── tu_tien.en.yaml
│   │   ├── litrpg.vn.yaml
│   │   ├── litrpg.en.yaml
│   │   ├── vu_su.vn.yaml
│   │   └── hien_dai.vn.yaml
│   ├── archetypes/             # Port from JP system, generalize
│   ├── examples/               # Few-shot per (genre × direction)
│   └── obsidian_template/      # Vault template to ship
│
├── scripts/
│   ├── run_ui.py
│   ├── import_vietphrase.py    # One-time dictionary import
│   ├── migrate_from_littrans.py
│   └── benchmark.py
│
└── tests/
    ├── unit/
    │   ├── test_qt_dict.py
    │   ├── test_pipeline.py
    │   └── ...
    └── integration/
```

---

## 8. Data Models (Key Schemas)

```python
# core/models/project.py
class Project(BaseModel):
    id: UUID
    name: str
    slug: str
    source_lang: Literal["zh", "vn", "en"]
    target_lang: Literal["vn", "en"]
    genre: Literal["tu_tien", "litrpg", "vu_su", "hien_dai", "other"]
    
    mode_default: Literal["convert", "polish", "side_by_side"] = "polish"
    
    provider_config: ProviderConfig
    style_pack_overrides: dict = {}
    custom_dict_files: list[Path] = []  # Per-novel custom .txt
    
    vault_path: Path                 # Obsidian vault location
    created_at: datetime
    updated_at: datetime

# core/models/chapter.py
class Chapter(BaseModel):
    id: UUID
    project_id: UUID
    index: int                       # 0001, 0002...
    
    source_text: str
    convert_text: str | None         # After Layer 1
    polished_text: str | None        # After LLM
    
    state: Literal["raw", "converted", "polished", "audited", "failed"]
    quality_score: float | None      # From post-call audit
    
    pre_call_artifact: dict | None   # Chapter Map JSON
    post_call_artifact: dict | None  # Audit results
    
    tokens_used: int = 0
    provider_used: str | None
    translated_at: datetime | None

# core/models/term.py
class Term(BaseModel):
    id: UUID
    project_id: UUID | None          # None = global, else per-novel
    
    category: Literal[
        "character", "skill", "realm", "place", 
        "item", "org", "system_msg", "phrase"
    ]
    
    locked: dict[str, str]           # {"zh": "金丹", "vn": "Kim Đan", "en": "Golden Core"}
    aliases: dict[str, list[str]] = {}
    
    source: Literal[
        "vietphrase",        # From VP dictionary
        "names_dict",        # From Names.txt
        "scout_extracted",   # AI extracted
        "manual",            # User added
        "imported"           # From other system
    ]
    
    confidence: float = 1.0
    first_seen_chapter: int | None
    locked_at: datetime
    notes: str = ""
```

---

## 9. UI Layer Design

### 9.1 Streamlit (operations dashboard)

**Pages:**
1. **Library** — list of projects, create/import
2. **Translate** — paste text or pick chapter range, choose mode (convert/polish), trigger
3. **Jobs** — live progress, queue, retry failed
4. **Dictionary** — upload QT dictionary files (VietPhrase.txt, Names.txt, ...), manage custom dict per novel
5. **Glossary** — per-novel locked terms (edit, add, conflict resolution)
6. **Settings** — API keys, model selection, rate limits
7. **Export** — EPUB build, copy-to-clipboard helpers, BBCode wrap

**Why Streamlit:** Quick to build, perfect for forms + monitoring. Not for content browsing.

### 9.2 Obsidian Vault (content workspace)

**Auto-generated structure per project:**
```
vault/projects/{project_slug}/
├── _config.md                   # Project metadata
├── _dashboard.md                # Dataview-powered overview
├── chapters/
│   ├── 0001.md                  # Source + Convert + Polished in callouts
│   └── ...
├── characters/                  # One file per character
├── skills/
├── realms/
├── places/
├── factions/
└── bible/
    ├── timeline.md
    ├── worldbuilding.md
    └── arcs/
```

**Why Obsidian:** Best UX for reading, editing, navigating, visualizing. Free.

### 9.3 Copy-Paste Output

For uploading to tangthuvien/sstruyen/wikidich:
- "Copy Convert" button — raw Hán-Việt
- "Copy Polished" button — final translation
- "Copy with BBCode" — wrapped for forum posting
- Plain text only, no markdown formatting that breaks paste

---

## 10. MVP Roadmap (6 weeks, focused)

### Week 1: Foundation
- [ ] Project scaffolding (pyproject, structure, CI)
- [ ] SQLite + SQLModel + Alembic migrations
- [ ] Pydantic models (Project, Chapter, Term, Job)
- [ ] Repository pattern setup
- [ ] Basic Streamlit shell with Library page

### Week 2: QT Dictionary Engine
- [ ] QT-format parser (VietPhrase.txt, Names.txt, LuatNhan.txt, etc.)
- [ ] Aho-Corasick automaton builder (use `pyahocorasick`)
- [ ] Priority-based replacement engine
- [ ] LuatNhan pattern matcher (regex with named params)
- [ ] CLI: `trilex import-dict ./VietPhrase.txt`
- [ ] **Acceptance test: convert 1 chương ZH → readable Hán-Việt in <100ms**

### Week 3: ZH→VN Pipeline (MVP route)
- [ ] Provider adapters (Gemini + Claude)
- [ ] ApiKeyPool (port from LiTTrans)
- [ ] Pipeline orchestrator (async)
- [ ] Pre-call, Trans-call, Post-call stages
- [ ] Style pack loader (YAML)
- [ ] Tu tiên style pack (priority #1)
- [ ] **Acceptance test: paste 1 chương ZH → polished VN in vault**

### Week 4: Obsidian Output + Glossary
- [ ] Vault file writer (frontmatter, callouts, wiki-links)
- [ ] Per-novel glossary extraction & storage
- [ ] Name lock validation
- [ ] Character file generation
- [ ] Streamlit: Translate + Jobs + Glossary pages
- [ ] **Acceptance test: 10 chương ZH → consistent glossary, all names locked**

### Week 5: Other Routes + UX Polish
- [ ] EN→VN route (port from LiTTrans logic)
- [ ] ZH→EN route (no Hán-Việt, direct LLM)
- [ ] VN→EN route
- [ ] Copy-to-clipboard buttons (plain + BBCode)
- [ ] EPUB export
- [ ] Settings page (API key management)
- [ ] **Acceptance test: each route translates 5 chương successfully**

### Week 6: Bible + Scout + Hardening
- [ ] Bible System (3-tier, port from LiTTrans)
- [ ] Scout AI (forward-reading every N chapters)
- [ ] Arc memory
- [ ] Error handling, retry logic
- [ ] Documentation (README, user guide)
- [ ] **Acceptance test: 50-chapter project with no manual intervention**

### Beyond MVP (optional)
- LitRPG style pack
- Vu Sư style pack
- Hiện đại style pack
- Trilingual side-by-side viewer
- Obsidian plugin (right-click translate)
- Site profile learner (port LiTTrans scraper)
- Web frontend (Next.js) for public deploy

---

## 11. Data Migration from LiTTrans

LiTTrans data structure → TriLex schema:
```
LiTTrans data/glossary/*.json   →   trilex.db: terms (source="imported")
LiTTrans data/characters/*.json →   trilex.db: terms (category="character")
LiTTrans data/bible/*           →   vault: bible/*.md
LiTTrans inputs/{novel}/        →   vault: projects/{slug}/chapters/ (as source)
LiTTrans outputs/{novel}/       →   vault: projects/{slug}/chapters/ (as polished)
```
Migration script: `scripts/migrate_from_littrans.py --from /path/to/littrans --to ./data/vault`

---

## 12. Decision Log (Confirmed)

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Single-user tool | Confirmed by user |
| Routes | 4 (ZH→VN, ZH→EN, EN→VN, VN→EN) | ZH never as target |
| Persistence | SQLite + Alembic | Solo user, transactional, fast |
| UI | Streamlit (ops) + Obsidian (content) | Hybrid, leverage strengths |
| Layer 1 | QT dictionaries (VietPhrase, Names, LuatNhan, ...) | User has them, ~1.14M entries |
| LLM role | Polish, not raw translate | Saves tokens, better consistency |
| Output modes | Convert + Polish + Side-by-side | Different use cases |
| Genre priority | Tu tiên first | Largest market, best with VP |
| Provider | Gemini default, Claude/DeepSeek optional | Free tier first |
| Async | Yes (asyncio + httpx) | Enables parallel chapters |
| Python version | 3.11+ | Modern type hints, performance |

---

## 13. Open Questions (For Later Sessions)

- Project name (TriLex is placeholder)
- Final tu tiên style pack content (need few-shot examples)
- Specific Obsidian vault template design
- Whether to build Obsidian plugin (Phase 3)
- Hosting/sharing strategy (if ever go public)

---

## 14. Quick Reference — What to Build First

If you have 1 weekend to prototype and validate the architecture:

```bash
# Day 1: QT dictionary engine standalone
1. pip install pyahocorasick pydantic
2. Build qt_dict/parser.py + automaton.py + applier.py
3. CLI: python -m trilex.qt_dict.cli convert input.txt
4. Validate: convert quality matches Wikidich

# Day 2: Add LLM polish
1. Build providers/gemini.py
2. Pipeline: convert → polish → output
3. Compare polished output vs raw Gemini translation
4. Measure: token savings, quality, consistency

If both checkpoints pass → architecture validated, proceed with full build.
```

---

**END BLUEPRINT v1.0**

*Generated 2026-05-01. Living document — update as decisions evolve.*
