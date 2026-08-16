# Bible Engine // Oracle

A local Bible and Second Temple research instrument. It keeps authority tiers physically and visually separate, uses a local searchable corpus for retrieval, fetches canonical quotations from the official ESV API, and uses your installed **Codex CLI / ChatGPT login** only as the synthesis layer.

## Current feature set

### Oracle core

- **Codex-only generation.** No Ollama, no alternate model fallback.
- **GPT-5.6 Luna** with configurable reasoning effort; medium is the default.
- **UTF-8-safe Codex transport.** Questions and retrieved passages are sent to Codex as explicit UTF-8 bytes.
- **Native Codex executable on Windows.** Bible Engine resolves npm's PowerShell/CMD shim to the packaged native `codex.exe` before passing configuration values.
- **Three authority shelves:**
  1. Canonical Scripture — 66-book Protestant canon; displayed and supplied to Codex in **ESV**.
  2. Deuterocanon / Apocrypha — public-domain WEB text, always labelled separately because canonical status varies by tradition.
  3. Second Temple / Pseudepigrapha — public-domain reference translations/context, always labelled **REFERENCE** rather than Scripture.
- Strict structured-output and evidence-ID validation prevents noncanonical evidence from being silently labelled canonical.

### Study Workspace — v0.4

Long-running studies are persistent local projects under `data/studies/`.

Each Study has:

- project objective and scope;
- pinned findings;
- context notes;
- open research questions;
- append-only consultation log;
- a generated `context.md` containing only curated project context;
- Markdown and JSON export.

The full research log is **not** sent to Codex on every request. Only the bounded curated context is included, and the prompt explicitly marks it as non-evidentiary. Every biblical claim still requires fresh corpus evidence.

### Original-Language Lab — v0.5

The **LANGUAGES** drawer adds word-level Biblical Hebrew/Aramaic and Koine Greek inspection.

It provides:

- ordered original-language word streams for canonical verses;
- surface form;
- lemma;
- Strong's tag where supplied by the source data;
- morphology code plus a readable high-level morphology description;
- deterministic transliteration for navigation/search;
- corpus-wide lemma occurrence lookup;
- search by original spelling, lemma, Strong's tag, normalized form, or transliteration;
- source/license provenance visible in the UI.

Sources installed locally by the launcher:

- **unfoldingWord Hebrew Bible (UHB v2.1.32)** — tokenized Hebrew/Aramaic USFM 3.0 with lexical/morphological metadata.
- **unfoldingWord Greek New Testament (UGNT v0.34)** — tokenized Koine Greek USFM 3.0 with lexical/morphological metadata.

The original-language corpus is a textual/linguistic evidence layer. It does not replace the ESV as Bible Engine's canonical English display/evidence translation, and morphology/lemma metadata is not itself an interpretive conclusion.

## One-click Windows start

Run:

```text
START_BIBLE_ENGINE.bat
```

The launcher:

1. verifies Python;
2. installs/updates the local Python environment;
3. installs Codex CLI if needed and resolves its native executable;
4. downloads/imports the complete public-domain WEB + ASV corpora if needed;
5. indexes the WEB Deuterocanon/Apocrypha separately from the 66-book canon;
6. installs/checks the public-domain Second Temple reference shelf;
7. installs/checks UHB + UGNT for the Original-Language Lab;
8. starts the local application at `http://127.0.0.1:8000` and opens your browser.

## ESV setup

Bible Engine deliberately does **not** place the copyrighted ESV text in this public repository or persist it in `bible.db`.

On first browser launch, open **Settings** and paste an ESV API key. Bible Engine validates it against the official ESV Passage Text API and stores the key only in:

```text
data/local_settings.json
```

That file is ignored by Git. Canonical passages are fetched from Crossway only for the current query. Bible Engine does not persist those ESV passages to its corpus database or Study logs.

The ESV API's usage/license conditions apply. Keep this project personal/non-commercial unless you separately obtain the rights appropriate to your use.

## Corpus architecture

### Canonical Scripture

- Local retrieval/index text: World English Bible (public domain)
- Display/evidence text: English Standard Version via official ESV API
- Original-language layer: UHB / UGNT
- Authority label: `CANONICAL`

The WEB copy is the local English search index. Before a canonical result is supplied to Codex or shown to the user, Bible Engine hydrates that reference from the ESV API.

### Deuterocanon / Apocrypha

The classic/ecumenical World English Bible source contains a Deuterocanon/Apocrypha section. Bible Engine imports and labels these separately, including works such as Tobit, Judith, Wisdom, Sirach, Baruch, the Maccabees, Esdras material, Prayer of Manasseh, Psalm 151, and Greek additions to Esther/Daniel where represented by the source USFM.

### Second Temple / pseudepigraphal reference shelf

The installer currently attempts a research-focused public-domain shelf including:

- 1 Enoch
- Jubilees
- Assumption/Testament of Moses
- Testaments of the Twelve Patriarchs
- Letter of Aristeas
- Apocalypse of Moses
- Ascension / Martyrdom of Isaiah
- Slavonic Life of Adam and Eve
- Books of Adam and Eve
- Sibylline Oracles
- contextual/excerpt sources for 2 Baruch and Psalms of Solomon

The UI shows source/translators and passage count for installed works. Context/excerpt sources are described as such; they are not silently presented as complete primary texts.

## Closed-corpus enforcement

Each Codex request runs in a fresh temporary directory with:

- `gpt-5.6-luna`
- configured reasoning effort
- web search disabled
- shell tool disabled
- subagents disabled
- user Codex config ignored
- project rules ignored
- ephemeral session
- read-only sandbox
- strict JSON output schema

Codex receives the user's question, the retrieved evidence rows, and—only when a Study is active—the bounded curated Study context.

Every substantive generated claim must cite supplied evidence IDs. Bible Engine validates those IDs and rejects a claim labelled `canonical` if supporting evidence comes from the Deuterocanon/reference shelf.

No prompt can erase a pretrained model's internal knowledge. The enforcement goal is provenance: outside knowledge may not count as evidence, and unsupported/mis-tiered structured claims are suppressed.

## Useful commands

```powershell
# regression tests
.\.venv\Scripts\python.exe -m pytest

# retry/install the reference shelf
.\.venv\Scripts\python.exe scripts\seed_reference_library.py

# install/rebuild Hebrew + Greek word index
.\.venv\Scripts\python.exe scripts\seed_original_languages.py

# corpus status
.\.venv\Scripts\python.exe scripts\check_corpus.py

# reference status
.\.venv\Scripts\python.exe scripts\check_reference_library.py

# original-language status
.\.venv\Scripts\python.exe scripts\check_original_languages.py

# Codex native executable resolution
.\.venv\Scripts\python.exe scripts\check_codex.py
```

GitHub Actions also runs the Python regression suite, Python compile check, and browser JavaScript syntax checks on pushes to `main` and pull requests.

## ESV copyright notice

Scripture quotations marked “ESV” are from the ESV® Bible (The Holy Bible, English Standard Version®), © 2001 by Crossway, a publishing ministry of Good News Publishers. Used by permission. All rights reserved. The ESV text may not be quoted in any publication made available to the public by a Creative Commons license. The ESV may not be translated into any other language.

Users may not copy or download more than 500 verses of the ESV Bible or more than one half of any book of the ESV Bible.
