# Bible Engine

A closed-corpus Bible research application that uses the **Codex CLI authenticated with your ChatGPT account** for synthesis. The Bible text remains in an inspectable local SQLite database. Codex receives only the Scripture passages retrieved for the current question and must return citation-bearing structured claims.

## Current architecture

```text
WEB + ASV Bible corpus (local SQLite)
        ↓
Exact reference + lexical retrieval
        ↓
Retrieved Scripture evidence only
        ↓
Codex CLI using your saved ChatGPT login
GPT-5.6 Luna · medium reasoning
        ↓
Schema + evidence-ID validation
        ↓
Answer with verse citations
```

There is **no Ollama provider and no generation fallback**. If Codex is missing, not authenticated through ChatGPT, unavailable, or fails, Bible Engine returns an error instead of silently switching to another model.

## One-click Windows start

Double-click:

```text
START_BIBLE_ENGINE.bat
```

The launcher will:

1. create/update the Python environment;
2. install Codex CLI with npm if Codex is not already installed;
3. check `codex login status`;
4. launch the official `codex login` ChatGPT OAuth flow if needed;
5. download and import the complete public-domain WEB + ASV translations if they are not already loaded;
6. start the local Bible Engine web app and open it in your browser.

The app runs at `http://127.0.0.1:8000`.

### Prerequisites

- Windows with Python 3.11+
- Internet access for first-run Bible downloads and Codex model calls
- Node.js/npm only if Codex CLI is not already installed
- A ChatGPT account with Codex access

Bible Engine **does not read, copy, or store your Codex OAuth tokens**. It launches the installed `codex` executable, which reuses the authentication already managed by Codex itself.

## Required Codex configuration

Defaults are hard-coded at the application layer and can be overridden only through Bible Engine environment variables:

```text
BIBLE_CODEX_MODEL=gpt-5.6-luna
BIBLE_CODEX_REASONING_EFFORT=medium
```

Each answer invokes `codex exec` with:

- `gpt-5.6-luna`
- `medium` reasoning effort
- ephemeral session storage
- read-only sandbox
- user/project Codex config ignored
- user/project exec rules ignored
- web search disabled
- shell tool disabled
- subagents disabled
- a JSON output schema

The subprocess runs in a fresh temporary empty directory. This prevents the Bible-answering run from using repository files, local notes, MCP configuration, web search, or shell commands as alternate evidence sources. Codex authentication remains available because authentication is separate from the ignored user config.

## Closed-corpus guarantee and limitation

Bible Engine enforces provenance architecturally:

- the Bible corpus is the only evidence retrieved by the application;
- each generated supported claim must cite one or more evidence IDs supplied in that request;
- unknown evidence IDs are rejected;
- uncited supported claims are rejected;
- malformed structured output is rejected;
- Codex web search and shell tools are disabled for the run.

A pretrained model still has internal knowledge. No prompt can erase that training. Bible Engine therefore constrains what may count as evidence and suppresses responses that violate the evidence/citation contract; this is stronger than merely prompting a generic chatbot to "use only the Bible," but it is not a mathematical proof that pretrained knowledge never influences wording.

## Included / installed corpus

The project uses two public-domain English translations:

- **WEB — World English Bible Classic**
- **ASV — American Standard Version (1901)**

The small demo excerpts in `data/demo/` exist only for automated tests. The normal Windows launcher requires the **complete** WEB + ASV corpora and downloads/imports them on first run.

The canonical importer keeps the standard 66-book Protestant canon and ignores deuterocanonical books present in some source distributions.

## Manual setup

If you do not use the Windows launcher:

```bash
python -m venv .venv
# activate the venv
pip install -e ".[dev]"
python scripts/fetch_public_domain.py
python scripts/seed_public_domain.py
codex login
uvicorn app.main:app --reload
```

## Optional similarity index

Normal operation uses exact-reference and SQLite FTS5 lexical retrieval. An optional deterministic local similarity index can be built without another AI provider:

```bash
python scripts/build_embeddings.py
```

It uses local hash vectors only. Codex remains the sole language-model provider.

## Import another translation

Only load text you are legally permitted to store/use.

### JSON

```json
{
  "verses": [
    {"book":"Genesis","chapter":1,"verse":1,"text":"..."}
  ]
}
```

```bash
python scripts/import_corpus.py \
  --code MYTR \
  --name "My Translation" \
  --input /path/to/translation.json \
  --license "Private licensed copy"
```

### USFM

Point `--input` to a directory containing `.usfm` or `.sfm` files.

## API

### `GET /api/health`

Reports corpus counts plus Codex installation, ChatGPT-auth status, model, and reasoning effort.

### `POST /api/ask`

```json
{
  "question": "Compare Jude 1:6 in WEB and ASV. What is explicit?",
  "translations": ["WEB", "ASV"],
  "top_k": 12,
  "context_radius": 1,
  "semantic": false
}
```

Successful generation mode is:

```text
codex_closed_corpus
```

If no relevant Scripture is retrieved, the result is `no_evidence`. Provider failures are HTTP errors; there is no alternate-model fallback.

## Tests

```bash
pytest
```

The tests cover reference parsing, exact and lexical retrieval, USFM ingestion, Codex provider isolation/flags, citation validation, invalid-output rejection, and required-provider behavior.
