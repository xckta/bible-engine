# Bible Engine // Oracle

A local Bible and Second Temple research instrument. It keeps authority tiers physically and visually separate, uses a local searchable corpus for retrieval, fetches canonical quotations from the official ESV API, and uses your installed **Codex CLI / ChatGPT login** only as the synthesis layer.

## What changed in v0.3

- **Codex-only generation.** No Ollama, no alternate model fallback.
- **GPT-5.6 Luna / medium** is the default.
- **UTF-8-safe Codex transport.** Questions and retrieved passages are sent to Codex as explicit UTF-8 bytes, avoiding Windows locale corruption from smart quotes, Greek, Hebrew, em dashes, etc.
- **Native Codex executable on Windows.** Bible Engine resolves npm's `codex.ps1` / `codex.cmd` shim to the packaged native `codex.exe` before passing TOML `--config` values.
- **Three evidence shelves:**
  1. Canonical Scripture — 66-book Protestant canon; displayed and supplied to Codex in **ESV**.
  2. Deuterocanon / Apocrypha — public-domain WEB text, always labelled separately because canonical status varies by tradition.
  3. Second Temple / Pseudepigrapha — public-domain reference translations/context, always labelled **REFERENCE** rather than Scripture.
- **Oracle UI.** Dark/gold research console, animated consultation state, corpus map, evidence ledger, authority/classification labels, and local settings.

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
6. attempts to install the public-domain Second Temple reference shelf;
7. starts the local application at `http://127.0.0.1:8000` and opens your browser.

A source site being temporarily unavailable does not prevent the Oracle from starting; missing reference works remain visible as absent/zero-count and can be retried by rerunning the reference installer.

## ESV setup

Bible Engine deliberately does **not** place the copyrighted ESV text in this public repository or persist it in `bible.db`.

On first browser launch, open **Settings** and paste an ESV API key. Bible Engine validates it against the official ESV Passage Text API, stores the key only in:

```text
data/local_settings.json
```

That file is ignored by Git. Canonical passages are fetched from Crossway only for the current query. Bible Engine does not persist those ESV passages to its corpus database.

The ESV API's usage/license conditions apply. Keep this project personal/non-commercial unless you separately obtain the rights appropriate to your use.

## Corpus architecture

### Canonical Scripture

- Local retrieval/index text: World English Bible (public domain)
- Display/evidence text: English Standard Version via official ESV API
- Authority label: `CANONICAL`

The WEB copy is only the local search index. Before a canonical result is supplied to Codex or shown to the user, Bible Engine hydrates that reference from the ESV API.

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

The UI shows the source/translators and passage count for every installed work. Context/excerpt sources are described as such; they are not silently presented as complete primary texts.

## Closed-corpus enforcement

Each Codex request runs in a fresh temporary directory with:

- `gpt-5.6-luna`
- `medium` reasoning effort
- web search disabled
- shell tool disabled
- subagents disabled
- user Codex config ignored
- project rules ignored
- ephemeral session
- read-only sandbox
- JSON output schema

Codex receives only the user's question plus the retrieved evidence rows.

Every substantive generated claim must cite supplied evidence IDs. Bible Engine validates those IDs and also rejects a claim labelled `canonical` if any supporting evidence is from the Deuterocanon or reference shelf.

No prompt can erase a pretrained model's internal knowledge. The enforcement goal is provenance: outside knowledge may not count as evidence, and unsupported/mis-tiered structured claims are suppressed.

## Useful commands

```powershell
# tests
.\.venv\Scripts\python.exe -m pytest

# retry/install the reference shelf
.\.venv\Scripts\python.exe scripts\seed_reference_library.py

# corpus status
.\.venv\Scripts\python.exe scripts\check_corpus.py

# reference status
.\.venv\Scripts\python.exe scripts\check_reference_library.py

# Codex native executable resolution
.\.venv\Scripts\python.exe scripts\check_codex.py
```

## ESV copyright notice

Scripture quotations marked “ESV” are from the ESV® Bible (The Holy Bible, English Standard Version®), © 2001 by Crossway, a publishing ministry of Good News Publishers. Used by permission. All rights reserved. The ESV text may not be quoted in any publication made available to the public by a Creative Commons license. The ESV may not be translated into any other language.

Users may not copy or download more than 500 verses of the ESV Bible or more than one half of any book of the ESV Bible.
