# TriLex — Research & Best Practices 🔬

> **Mục đích**: Compile các best practices từ những tool dịch tiểu thuyết nổi tiếng nhất trên GitHub, các kỹ thuật name lock chuyên nghiệp, và tips tối ưu cho từng model AI cụ thể.
>
> **Cách dùng**: Đây là reference khi build từng feature. Khi đến Phase 2-5 trong ROADMAP, mở file này tham chiếu.

---

## 📚 PHẦN 1 — Các Tool Tham Khảo (Đã Research)

### 1.1 GalTransl ⭐⭐⭐⭐⭐ (Must-study)
- **GitHub**: https://github.com/GalTransl/GalTransl (2.1k stars)
- **Mục đích gốc**: Dịch Galgame (visual novel) Nhật → Trung
- **Tại sao quan trọng**: Đây là tool MA THUẬT về prompt engineering cho LLM translation. Họ đã giải quyết 90% vấn đề bạn sẽ gặp.

**Features bạn nên copy**:

#### a) GPT Dictionary System (TUYỆT ĐỐI PHẢI HỌC)
Đây là innovation lớn nhất của GalTransl. Format:
```
日文[Tab]中文[Tab]解释(可选)
```
Ví dụ:
```
フラン	芙兰	name, lady, teacher
笠間	笠间	last name of 笠間陽菜乃, girl
陽菜乃	阳菜乃	first name of 笠間陽菜乃, girl
あたし	我/人家	use '人家' when being cute
```

**Insight quan trọng**:
- Không chỉ map từ → từ, mà còn **giải thích context** cho AI
- Chỉ inject vào prompt khi từ đó **xuất hiện trong câu hiện tại** (tiết kiệm token)
- Tách riêng "Dictionary chung" (cho mọi project) và "Dictionary project" (per-novel)

**Cho TriLex (ZH→VN)**: Adapt thành format
```
中文[Tab]越文[Tab]Mô tả
李青	Lý Thanh	tên nhân vật chính, nam, đệ tử của Trương Lão
青云宗	Thanh Vân Tông	tông môn của main character
```

#### b) 4-Layer Dictionary System
```
Pre-translation dictionary  →  Áp dụng trên RAW source TRƯỚC khi dịch
                                (sửa typo, normalize variant)

GPT dictionary              →  Inject vào prompt LLM (như guide)

Post-translation dictionary →  Replace sau khi LLM dịch xong
                                (force consistency)

Conditional dictionary      →  Replace có điều kiện (only if X exists)
                                Format: pre_jp/post_jp[tab]条件[tab]找[tab]替换
```

**Cho TriLex**: Đây là kiến trúc 4 layers thay vì 1. Ưu điểm:
- Pre-dict: fix encoding bugs, typos trước
- GPT-dict: tận dụng AI hiểu context
- Post-dict: hard-lock, đảm bảo 100% consistency
- Conditional: handle ambiguous (1 từ ZH có 2 nghĩa khác context)

#### c) Cache + Resume System
Mỗi câu dịch xong lưu vào cache JSON:
```json
{
    "index": 4,
    "name": "speaker_name",
    "pre_jp": "raw original",
    "post_jp": "after pre-dict",
    "pre_zh": "AI translation 1",
    "proofread_zh": "AI translation 2 (proofread pass)",
    "trans_by": "DeepSeek-V3",
    "proofread_by": "Claude-Opus",
    "problem": "残留日文" // auto-detected issues
}
```

**Lợi ích**: 
- Crash giữa chừng → resume không mất data
- Muốn re-translate 1 câu → xóa `pre_zh` field, restart
- Audit trail đầy đủ

#### d) Auto Problem Detection
Sau dịch, tự động scan problems:
```yaml
problemList:
  - 词频过高     # word frequency abnormal
  - 标点错漏     # punctuation issues
  - 残留日文     # untranslated source remains
  - 丢失换行     # missing line breaks
  - 多加换行     # extra line breaks
  - 比日文长     # output >1.3x longer than input (suspicious)
  - 字典使用     # ignored glossary
  - 语言不通     # wrong target language
```

**Cho TriLex** (adapt cho Việt):
```yaml
- 残留中文      # còn chữ Hán chưa dịch
- 残留英文      # English còn sót
- 词频过高      # từ lặp lại bất thường
- 名字不一致    # tên không match glossary
- Hán-Việt mixing  # lẫn lộn pure Việt với Hán-Việt
- Translationese # "một cách", "có vẻ như"
```

#### e) Two-Pass Translation (Translate + Proofread)
```
Pass 1: Dùng model rẻ (Gemini Flash, DeepSeek) dịch nhanh → pre_zh
Pass 2: Dùng model đắt (Claude Opus) proofread + polish → proofread_zh
```

Tiết kiệm 70% chi phí mà chất lượng tương đương dùng Claude từ đầu.

---

### 1.2 LexiconForge ⭐⭐⭐⭐
- **GitHub**: https://github.com/anantham/LexiconForge
- **Đặc điểm**: Web app TypeScript, multi-provider support (Gemini, Claude, DeepSeek, OpenRouter)

**Features đáng học**:

#### a) Real-time Cost Tracking
Hiển thị chính xác từng request tốn bao nhiêu (đến phần nghìn cent). Quan trọng cho người dùng trả tiền.

#### b) Cancelable Requests
Click "abort" giữa chừng request đang chạy. Tránh tốn tiền cho output không cần.

#### c) Compare with Fan Translations
Toggle giữa 3 versions: AI / Raw / Fan translation. Cực hữu ích để benchmark.

#### d) Adjustable Context Depth
0-5 chương trước làm context. Bạn chọn balance giữa chất lượng và token cost.

#### e) Surgical Edit
Click vào câu cụ thể để edit chỉ câu đó (không re-translate cả chương).

---

### 1.3 bilingual_book_maker ⭐⭐⭐⭐
- **GitHub**: https://github.com/yihong0618/bilingual_book_maker (~7k stars)
- **Đặc điểm**: Tạo bilingual EPUB (song ngữ), nhiều providers

**Features đáng học**:

#### a) Running Context Summarization
```
--use_context flag:
- Chương 1: Send full passage → Summarize ý chính (1 paragraph)
- Chương 2+: Update summary với chi tiết mới
- Mỗi request: Send summary + current chapter
```

Insight: Thay vì send N chương đầy đủ làm context, chỉ send 1 paragraph summary. Tiết kiệm token cực kỳ.

#### b) Parallel Workers
```
--parallel-workers 4
```
4 chương chạy song song, đảm bảo output thứ tự đúng.

#### c) API Key Rotation
```
--openai_key key1,key2,key3
```
Nhiều keys → rotate → giảm rate limit error.

#### d) Resume Capability
```
--resume
```
Nếu fail giữa chừng, restart không mất công.

---

### 1.4 ebook-GPT-translator ⭐⭐⭐
- **GitHub**: https://github.com/jesselau76/ebook-GPT-translator
- **Đặc điểm**: SQLite cache, glossary CSV/XLSX

**Features đáng học**:

#### a) SQLite Cache as Resume Mechanism
Database làm cache thay vì JSON files. Reliable hơn, query nhanh hơn.

#### b) Auto-detection of Resume Point
```
trilex check resume → tự động đoán chương nào tiếp theo cần dịch
```

#### c) Live Progress (cả block + chunk)
UI hiển thị progress 2 levels: chương nào, đoạn nào trong chương. Không bao giờ bị "treo".

#### d) Custom Prompt Box
User có thể type custom instruction như "Dịch theo phong cách Hồng Lâu Mộng".

---

### 1.5 Sakura/GalTransl Local Models ⭐⭐⭐
- **GitHub**: https://github.com/SakuraLLM/SakuraLLM
- **Đặc điểm**: Local LLM (offline), specialized cho JP→ZH translation

**Lessons learned**:

#### a) Specialized Prompts (KEY INSIGHT)
Không dùng prompt generic "Translate this to X". Dùng prompt **được tune cho task cụ thể**:

```
You are a light novel translation model, can fluently and smoothly 
translate Japanese text into Chinese in the style of Japanese light novels, 
and correctly use pronouns in context, without adding pronouns that are 
not in the original text.
```

3 yếu tố quan trọng:
1. **Persona**: "light novel translation model"
2. **Style**: "in the style of Japanese light novels"
3. **Constraint**: "without adding pronouns that are not in the original text"

#### b) Batch Translation 7-10 Lines
Optimal batch size: 7-10 dòng/request. Không phải càng nhiều càng tốt.

#### c) Frequency Penalty for Degeneration
Nếu LLM bắt đầu lặp lại bất thường (degeneration):
```
frequency_penalty: 0.1 - 0.2
```

---

### 1.6 OpenNovel & Webnovels AI ⭐⭐⭐
- **URL**: https://opennovel.co, https://webnovelsai.com
- **Đặc điểm**: Web SaaS, browser extension cho fetch chương

**UX features đáng học**:

#### a) "Fetch Next Chapter" Button
Click 1 phát tự động crawl chương tiếp theo. Quan trọng cho user binge-reading.

#### b) Browser Extension cho login-required sites
Extension chạy trong browser của user → bypass paywall hợp pháp (vì user đã login).

#### c) Auto-detect Characters & Terms
Pre-scan novel → suggest glossary entries. User confirm → lock.

#### d) NSFW Handling Strategy
Có model fallback (Google/Bing Translate) cho content censored. Đảm bảo không có "[scene removed]".

---

## 🎯 PHẦN 2 — Name Lock & Glossary Best Practices

Đây là vấn đề khó nhất. Compile từ tất cả tool trên:

### 2.1 Multi-Tier Glossary Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ TIER 1 — UNIVERSAL DICT (chung cho mọi project)              │
│   Ví dụ: 道友→đạo hữu, 师父→sư phụ                          │
│   Source: Built once, share across all translations          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ TIER 2 — PROJECT GLOSSARY (per-novel)                        │
│   Ví dụ: 李青→Lý Thanh, 青云宗→Thanh Vân Tông              │
│   Source: Auto-extracted (Scout) + manual edit               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ TIER 3 — CHAPTER GLOSSARY (auto-built per chapter)           │
│   Chỉ extract terms xuất hiện trong chương hiện tại          │
│   Send vào prompt → tiết kiệm token                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Three-Layer Name Lock Enforcement

Để tên KHÔNG BAO GIỜ bị dịch sai, cần lock ở 3 chỗ:

#### Layer 1: Pre-translation (deterministic)
Apply QT dictionary với highest priority cho project glossary.
```python
# Pseudo-code
text = apply_replacement(text, project_glossary, priority=HIGHEST)
text = apply_replacement(text, qt_dict, priority=NORMAL)
```

#### Layer 2: Prompt Engineering
Inject glossary vào LLM prompt với **constraint cứng**:
```
**MANDATORY GLOSSARY** (you MUST use these exact translations):
- 李青 → Lý Thanh (NEVER: Lý Xanh, Li Qing, or any other variant)
- 青云宗 → Thanh Vân Tông (NEVER: Sect of Blue Cloud, Qing Yun Sect)

If you encounter these terms in the source, you MUST output the locked 
translation. Failure to do so is a critical error.
```

#### Layer 3: Post-validation (deterministic)
Sau khi LLM trả về, scan output:
```python
def validate_name_lock(output_text, glossary):
    violations = []
    for term in glossary:
        # Check nếu source xuất hiện nhưng locked translation không xuất hiện
        if term.source in original and term.locked not in output_text:
            violations.append(term)
    return violations

if violations:
    # Auto-fix bằng regex replace
    for v in violations:
        output_text = re.sub(forbidden_variant, v.locked, output_text)
```

### 2.3 Aliases Handling (Quan trọng cho character names)

1 nhân vật có nhiều cách gọi:
```yaml
char: ch_li_qing
locked: Lý Thanh
aliases_zh:
  - 李青       # full name
  - 小青       # nickname (Tiểu Thanh)
  - 青弟       # familiar (Thanh đệ)
  - 青儿       # affectionate
context_translations:
  小青: "Tiểu Thanh"  # GIỮ Tiểu, không dịch là "Little Thanh"
  青弟: "Thanh đệ"
  青儿: "Thanh nhi"
```

Insight: AI cần biết các aliases này thuộc về cùng 1 character, và dịch sao cho consistent.

### 2.4 Conflict Resolution

Khi 1 từ có 2 nghĩa khác nhau theo context:
```yaml
ambiguous_term: 道
contexts:
  - condition: "preceded by 修, 悟, 求"
    translate: "đạo (path of cultivation)"
  - condition: "preceded by 大, 街, 街道"
    translate: "đường, phố"
  - default: "đạo"
```

GalTransl gọi đây là **Conditional Dictionary**.

### 2.5 Auto-Extraction Pipeline (Scout)

Phải có 1 background process auto-discover terms:

```
Mỗi N chương dịch xong:
  1. Send batch của chương đó cho LLM với prompt:
     "List all proper nouns (characters, places, sects, items, skills) 
      that appear in this text. Output JSON với fields:
      {term, type, suggested_vn, suggested_en, frequency, first_appearance}"
  
  2. Compare với existing glossary
     → Nếu mới: add vào "Pending Review"
     → Nếu có conflict: flag warning
  
  3. UI hiển thị "Pending" → User accept/reject/edit
  
  4. Locked terms → apply cho chương sau
```

---

## 🤖 PHẦN 3 — Model-Specific Tips (Crucial)

Mỗi LLM có "cá tính" khác nhau. Prompt cho Gemini không tốt với Claude, ngược lại.

### 3.1 Model Comparison cho Translation Tasks

| Model | Mạnh nhất | Yếu nhất | Cost | Verdict |
|-------|-----------|----------|------|---------|
| **Claude Opus 4.7** | Literary, văn vẻ, "lexical taste" | Đắt | $$$$ | Best for FINAL polish |
| **Claude Sonnet 4.6** | Balance quality/cost | Đôi khi dài dòng | $$$ | Daily driver cho Việt |
| **GPT-5.4** | Versatile, broad knowledge | Generic style | $$$$ | Best all-around |
| **DeepSeek V4** | ZH→anything, RẺ NHẤT | Lệch về văn phong TQ | $ | **#1 cho ZH source** |
| **Gemini 2.5 Pro** | Long context (1M tokens) | Hay refuse content | $$ | Bulk translation |
| **Gemini 2.5 Flash** | Cực rẻ, nhanh | Quality kém hơn Pro | ¢ | Pre-call, scout |
| **Sakura local** | Free, offline, JP-specialized | JP→ZH only, cần GPU | Free | Niche |

### 3.2 Tips theo Model

#### A) Claude (Opus/Sonnet) — "The Literary Translator"

**Mạnh**:
- Hiểu nuance, ẩn dụ, double meaning
- Văn phong tự nhiên, ít "translationese"
- Theo style guide rất tốt

**Yếu**:
- Hay tự thêm interpretation (over-translate)
- Refuse NSFW gắt
- Đắt

**Prompt tips**:
```python
# Claude works best with structured XML-like instructions
prompt = """
<role>
You are an expert literary translator specializing in Chinese cultivation novels.
</role>

<task>
Translate the following text from Chinese to Vietnamese, polishing the rough 
convert provided.
</task>

<context>
{recent_chapter_summary}
</context>

<glossary>
{relevant_terms}
</glossary>

<style_guide>
- Use Hán-Việt vocabulary for cultivation terms
- Maintain "đạo hữu" not "fellow Daoist"
- Sentence structure should follow Vietnamese, not literal Chinese
</style_guide>

<source>
{original_zh}
</source>

<rough_convert>
{qt_pass_output}
</rough_convert>

<output_format>
Output ONLY the polished Vietnamese translation. No commentary, no preamble.
</output_format>
"""
```

**Settings**:
- Temperature: 0.3-0.5 (cao hơn → creative; thấp hơn → faithful)
- Max tokens: chương ngắn 4000, dài 8000

---

#### B) Gemini (Pro/Flash) — "The Bulk Worker"

**Mạnh**:
- Context window cực lớn (1M tokens) → nhồi cả glossary + 5 chương context
- Rẻ, free tier hào phóng
- Multimodal (input image cũng được)

**Yếu**:
- Hay refuse content "sensitive" (cảnh chiến đấu, tu tiên có máu)
- Style hơi flat/generic
- Đôi khi ignore instructions phức tạp

**Prompt tips**:
```python
# Gemini works best with clear, numbered instructions
prompt = """
TASK: Translate Chinese to Vietnamese.

INSTRUCTIONS:
1. Use the locked glossary EXACTLY as given
2. Keep cultivation terminology in Hán-Việt
3. Maintain natural Vietnamese sentence flow
4. Do NOT add explanations or notes

GLOSSARY (use these translations):
李青 = Lý Thanh
青云宗 = Thanh Vân Tông
[... etc]

CONTEXT (previous chapter summary):
{summary}

SOURCE TEXT:
{original}

ROUGH TRANSLATION (polish this):
{qt_output}

OUTPUT (Vietnamese only, no preamble):
"""
```

**Settings**:
- Temperature: 0.4-0.6
- Safety settings: tắt hoặc relax (else dễ bị refuse)
```python
safety_settings = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
}
```

---

#### C) DeepSeek V4 — "The Chinese Specialist"

**Mạnh**:
- Tokenizer optimized cho ZH → 20-40% rẻ hơn cho ZH content
- Hiểu cultural context Trung Quốc cực tốt (xian xia, wuxia, lịch sử)
- COMET score cao nhất cho ZH ↔ EN

**Yếu**:
- Lệch về phong văn TQ (đôi khi quá literal)
- Không tốt cho non-Chinese pairs (EN→VN dùng Claude tốt hơn)
- "Corner bracket bug" — đôi khi giữ nguyên 「」 không convert

**Prompt tips**:
```python
# DeepSeek hiểu prompt tiếng Trung tốt hơn tiếng Anh
prompt_zh = """
任务：将中文小说章节翻译成越南语。

要求：
1. 严格遵守词汇表（人名、地名、宗门名）
2. 保持仙侠/玄幻氛围
3. 越南语句式流畅自然
4. 汉越词优先（如：道友→đạo hữu）

词汇表：
{glossary}

原文：
{source}

输出（仅越南语）：
"""
```

**Settings**:
- Temperature: 0.3 (cần precision cho ZH)
- Use `deepseek-chat` cho dịch, `deepseek-reasoner` cho complex/poetry

---

#### D) Local Models (Sakura, Qwen) — "The Privacy Option"

**Khi nào dùng**:
- NSFW content (online APIs refuse)
- Privacy concerns
- Bulk translate offline (no API cost)

**Setup**:
- Sakura GalTransl 7B: cần 6GB VRAM (RTX 3060+)
- Qwen 2.5 14B: cần 12GB VRAM
- Chạy qua llama.cpp hoặc Ollama

**Prompt tips**:
```python
# Local models cần prompt rất specific
prompt = """### Instruction:
Translate the following Chinese light novel text to Vietnamese.
Preserve all formatting, line breaks, and proper nouns.

### Input:
{source}

### Response:
"""
```

**Settings**:
- Temperature: 0.1-0.2 (local models dễ degenerate)
- Frequency penalty: 0.1-0.2
- Repeat penalty: 1.1

---

### 3.3 Multi-Model Pipeline Strategy

**Production-grade strategy** (theo GalTransl + LexiconForge):

```
┌────────────────────────────────────────────────────────────┐
│ STAGE 1 — Scout (cheap & fast)                              │
│   Model: Gemini Flash hoặc DeepSeek-Flash                   │
│   Task: Extract terms, summarize, detect language            │
│   Cost: Negligible                                           │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 2 — Initial Translation (balanced)                     │
│   Model: Gemini Pro (cho ZH/EN→VN), DeepSeek (cho ZH→EN)    │
│   Task: First pass translation                               │
│   Cost: Moderate                                             │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 3 — Polish/Proofread (premium)                        │
│   Model: Claude Sonnet hoặc Opus                             │
│   Task: Style refinement, fix awkward phrases                │
│   Cost: Higher (chỉ chạy nếu user request "premium")        │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 4 — Validate (free, deterministic)                    │
│   Model: NONE (regex + glossary check)                      │
│   Task: Name lock validation, problem detection              │
│   Cost: Free                                                  │
└────────────────────────────────────────────────────────────┘
```

**User chọn tier**:
- **Economy** (free): Stage 1 + 2 với Gemini Flash + Free QT pass
- **Standard** (default): Stage 1 (Gemini Flash) + Stage 2 (Gemini Pro)
- **Premium** (paid): Full 4 stages với Claude polish

---

## 🛠️ PHẦN 4 — Features Đề Xuất Bổ Sung

Compile từ tất cả tools trên, đây là features bạn nên thêm vào TriLex:

### 4.1 Must-have (Tier 1)

#### a) **Two-Pass Translation Mode**
- Pass 1: Quick draft với cheap model
- Pass 2: Polish với premium model
- User chọn mode, hoặc auto-pick based on confidence

#### b) **Cache + Resume System**
- Mỗi câu/đoạn lưu cache JSON hoặc SQLite
- Crash → resume không mất data
- "Re-translate này" = xóa cache entry, restart

#### c) **Auto Problem Detection**
- Sau dịch, scan các vấn đề phổ biến
- Highlight trong UI cho user review
- Batch retranslate với key="problem_type"

#### d) **Context Summary Memory**
- Summarize chương trước (1 paragraph)
- Update summary tăng dần
- Inject vào mỗi prompt → consistency cross-chapter

#### e) **Multi-Provider with Fallback**
- Primary: Gemini
- Fallback 1: DeepSeek (nếu Gemini quota out)
- Fallback 2: Local Sakura (nếu offline)

### 4.2 Nice-to-have (Tier 2)

#### f) **Real-time Cost Tracker**
- Hiển thị cost từng request
- Daily/monthly budget alert
- Estimate cost cho job lớn trước khi run

#### g) **Cancelable Requests**
- Click "Stop" giữa chừng → abort, không charge

#### h) **Side-by-side Comparison**
- View 3 columns: Source | Convert | Polish
- Hoặc 2 cột: AI v1 vs AI v2 (cho proofread mode)

#### i) **Browser Extension cho Fetch Chapter**
- Cho sites có paywall (user login → extension extract)
- Auto-fetch next chapter

#### j) **Inline Edit**
- Click câu dịch → modal edit
- Save → update glossary nếu có change name

#### k) **EPUB Export với Bilingual Mode**
- Mỗi chương: paragraph ZH → paragraph VN xen kẽ
- Hoặc 2 column layout
- Phục vụ học tiếng (đọc song ngữ)

### 4.3 Advanced (Tier 3)

#### l) **Quality Scoring + Auto-retry**
- Mỗi chương: LLM judge tự score 1-5
- Score < 3 → auto-retry với premium model
- Score < 2 → flag for manual review

#### m) **Plugin System**
- User viết Python plugin riêng (pre/post process)
- GalTransl đã có ý tưởng này từ v4

#### n) **Custom Style Adaptation**
- Upload sample translation user thích → AI infer style
- Apply style đó cho future translations

#### o) **Cultural Footnotes Generation**
- AI tự generate TL notes cho terms khó
- Format: `Term* (*TL: explanation)`

---

## 📊 PHẦN 5 — Recommended Stack cho TriLex

Dựa trên research, stack đề xuất cuối cùng:

### Default Provider Strategy

```yaml
providers:
  scout:        # Term extraction, summary
    primary: gemini-2.5-flash
    fallback: deepseek-chat
    cost_tier: cheap
  
  translate:    # Main translation
    zh_to_vn:
      primary: deepseek-v4-pro  # Best for ZH source
      fallback: gemini-2.5-pro
    zh_to_en:
      primary: deepseek-v4-pro  # Best COMET
      fallback: gpt-5.4
    en_to_vn:
      primary: claude-sonnet-4.6  # Best for VN literary
      fallback: gemini-2.5-pro
    vn_to_en:
      primary: claude-sonnet-4.6
      fallback: gpt-5.4
    cost_tier: balanced
  
  polish:       # Premium polish (optional)
    primary: claude-opus-4.7
    fallback: claude-sonnet-4.6
    cost_tier: premium
  
  audit:        # Quality check
    primary: gemini-2.5-flash
    fallback: deepseek-chat
    cost_tier: cheap
```

### Default Pipeline

```
ZH source → 
  QT pass (free) → 
  Scout extract terms (Flash) → 
  Translate (DeepSeek) → 
  [Optional] Polish (Claude) → 
  Validate (regex) → 
  Output to vault
```

### Quality vs Cost Modes

```yaml
modes:
  free:
    description: "Convert only, no AI"
    pipeline: [qt_pass]
    cost: 0
  
  cheap:
    description: "QT + Gemini Flash polish"
    pipeline: [qt_pass, polish_with_gemini_flash]
    cost: ~$0.001/chapter
  
  standard:    # Default
    description: "Full pipeline với DeepSeek"
    pipeline: [qt_pass, scout, translate_deepseek, validate]
    cost: ~$0.01/chapter
  
  premium:
    description: "Full pipeline + Claude polish"
    pipeline: [qt_pass, scout, translate_deepseek, polish_claude, validate]
    cost: ~$0.05/chapter
  
  paranoid:
    description: "2-pass với Claude proofreading"
    pipeline: [qt_pass, scout, translate_v1, translate_v2, compare, validate]
    cost: ~$0.15/chapter
```

---

## 📝 PHẦN 6 — Universal Best Practices (Tổng Hợp)

### 6.1 Prompt Engineering Rules

1. **Always provide examples** (few-shot > zero-shot)
2. **Be specific about constraints** ("MUST use X" > "use X")
3. **Ask for output format explicitly** ("JSON only" > "give me data")
4. **Use structure**: Claude likes XML tags, Gemini likes numbered lists
5. **Repeat critical rules at the end** (recency bias)
6. **Use negative examples** ("DO NOT translate as Y") khi cần

### 6.2 Token Optimization

1. **Don't send full glossary** — chỉ send terms xuất hiện trong chương
2. **Don't send full history** — chỉ send 1-paragraph summary
3. **Use cheap model cho simple tasks** (Flash cho extract, Opus cho polish)
4. **Batch requests** khi possible (7-10 lines/batch theo Sakura research)
5. **Cache aggressively** — không retranslate cùng đoạn 2 lần

### 6.3 Quality Assurance

1. **Always have validate step** sau LLM (regex check name lock)
2. **Auto-detect common problems** (untranslated remnants, length anomaly)
3. **Maintain audit trail** (which model translated which chapter when)
4. **Allow easy rollback** (cache là source of truth, output regenerate được)
5. **Sample manually periodic** (mỗi 10 chương, đọc 1 chương random)

### 6.4 User Experience

1. **Progress indicators ALWAYS** (cả block + chunk level)
2. **Cancelable operations** (don't waste user money)
3. **Cost visibility** (show before + after each request)
4. **Resume on crash** (assume user will close laptop)
5. **Side-by-side comparison** (build trust, allow review)

### 6.5 Architecture Lessons

1. **Multi-tier dictionary** (universal + project + chapter)
2. **Multi-pass pipeline** (cheap draft + premium polish)
3. **Multi-provider fallback** (don't lock-in to 1 vendor)
4. **Plugin/extensibility** (user contributions are gold)
5. **Local-first storage** (privacy + control)

---

## 🎯 PHẦN 7 — Action Items cho TriLex

Bổ sung vào ROADMAP, tích hợp các best practices trên:

### Update Phase 1 (QT Engine)
- [ ] Thêm support cho **4-tier dict** (pre-trans, GPT-style, post-trans, conditional)
- [ ] Adapt format từ GalTransl: `源[Tab]目标[Tab]描述`

### Update Phase 2 (LLM Polish)
- [ ] Implement **2-pass mode** (cheap + premium)
- [ ] Implement **multi-provider routing** theo direction
- [ ] **Model-specific prompt templates** (Claude XML, Gemini numbered)
- [ ] **Safety settings disable** cho Gemini

### Update Phase 3 (Persistence)
- [ ] **Cache schema chi tiết** như GalTransl (pre_jp, post_jp, pre_zh, proofread_zh, problem)
- [ ] **Resume detection** auto

### Update Phase 4 (UI)
- [ ] **Real-time cost tracker** sidebar
- [ ] **Cancelable requests** (Stop button)
- [ ] **Side-by-side viewer** (3 columns)
- [ ] **Inline edit modal**

### Update Phase 5 (Other Routes)
- [ ] **Auto problem detection** với 8 categories adapted cho VN
- [ ] **Browser extension stub** (Phase 2 future)

### New Phase 6 Additions
- [ ] **Plugin system** (Python entry points)
- [ ] **Quality auto-scoring + retry**
- [ ] **Bilingual EPUB export mode**

---

## 🏆 Top Repos to Star & Study

Trước khi bắt đầu code, vào GitHub star các repo này:

1. ⭐ https://github.com/GalTransl/GalTransl — **MUST READ source code**
2. ⭐ https://github.com/SakuraLLM/SakuraLLM — Local model deployment
3. ⭐ https://github.com/anantham/LexiconForge — UX inspiration
4. ⭐ https://github.com/yihong0618/bilingual_book_maker — Multi-provider patterns
5. ⭐ https://github.com/jesselau76/ebook-GPT-translator — SQLite cache patterns
6. ⭐ https://github.com/mayocream/koharu — Multi-provider modern (Rust nhưng đáng học)
7. ⭐ https://github.com/neavo/KeywordGacha — Auto glossary extraction tool

**Lưu ý**: Đừng copy code 1:1 (license khác nhau). Học **patterns + ideas**, implement lại bằng code của bạn.

---

## 📚 Reading List trước khi code

1. **GalTransl Wiki** — https://github.com/xd2333/GalTransl/wiki
   Đặc biệt: GPT Dictionary writing guide
2. **Sakura Prompt Format** — https://huggingface.co/SakuraLLM
3. **Gemini Best Practices** — https://ai.google.dev/docs/prompting_practices
4. **Anthropic Prompt Library** — https://docs.claude.com/en/prompt-library
5. **Translation benchmarks** — https://tokenmix.ai/blog/best-llm-for-translation

Đọc 5 link này = trước khi viết dòng code đầu tiên, bạn đã có base knowledge tốt hơn 90% người làm tool tương tự.

---

**END RESEARCH DOCUMENT**

*Cập nhật lần cuối: 2026-05-02. Khi gặp feature mới ở repo nào hay → add vào file này.*
