# Bible Only Engine

A local-first, closed-corpus Bible research application. It is deliberately **not** a Bible-fine-tuned LLM. Scripture lives in an inspectable SQLite database; retrieval selects evidence; an optional local Ollama model can synthesize an answer only through a citation-bearing JSON contract.

## Core guarantees

- Bible text is stored as verse-addressable rows in SQLite.
- Exact references (`Jude 1:6`, `2 Peter 2:4-7`) bypass fuzzy search.
- SQLite FTS5 provides lexical retrieval.
- Semantic retrieval can use Ollama embeddings, stored locally in SQLite.
- If Ollama is unavailable, the app returns retrieved Scripture only.
- Evidence-only mode can disable model synthesis even when Ollama is available.
- Generated claims must cite supplied evidence IDs; unknown or missing citations cause the generated answer to be rejected.
- The model is instructed to distinguish explicit statements from inference and to say when the loaded corpus does not establish a claim.
- No web search, commentary database, or external retrieval is built into the application.

> Important limitation: no prompt can erase a pretrained model's internal knowledge. The enforcement here is architectural: only approved corpus passages are supplied as evidence, every displayed generated claim must cite retrieved evidence, and malformed/uncited model output is suppressed. This materially reduces unsupported answers but is not a formal proof that a model never used prior knowledge while phrasing a cited claim.

## Included corpus

The repository includes **small demo excerpts** from two public-domain English translations so tests and the UI run offline:

- WEB — World English Bible Classic
- ASV — American Standard Version (1901)

The full public-domain texts are intentionally fetched from eBible.org during setup rather than duplicated in this repository. Run the commands below to install the complete translations. The current canonical book map imports the standard 66-book Protestant canon and ignores deuterocanonical books present in some WEB distributions.

## Quick start

### Windows PowerShell

```powershell
cd bible-only-engine
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts\seed_demo.py
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

### macOS / Linux

```bash
cd bible-only-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python scripts/seed_demo.py
uvicorn app.main:app --reload
```

## Load the complete WEB + ASV corpora

With internet access:

```bash
python scripts/fetch_public_domain.py
python scripts/seed_public_domain.py
```

Then optionally build embeddings:

```bash
# fully offline deterministic sparse-ish hash embeddings
python scripts/build_embeddings.py --provider hash

# OR, after installing/running Ollama and pulling an embedding model
python scripts/build_embeddings.py --provider ollama
```

The default database is `data/bible.db`.

## Ollama

The application talks to the local Ollama HTTP API at `http://localhost:11434` by default.

Example model setup:

```bash
ollama pull gemma3:4b
ollama pull embeddinggemma
```

Copy `.env.example` values into your shell/environment if you want different model names. The app does not require Ollama to start; without it, answers are extractive retrieval results only.

## Import another translation

Only load text you are legally permitted to store/use.

### JSON format

```json
{
  "verses": [
    {"book":"Genesis","chapter":1,"verse":1,"text":"..."}
  ]
}
```

Import:

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
Returns corpus counts and whether local Ollama is reachable.

### `GET /api/translations`
Lists loaded translations.

### `POST /api/ask`

```json
{
  "question": "Compare Jude 1:6 in WEB and ASV. What is explicit?",
  "translations": ["WEB", "ASV"],
  "top_k": 12,
  "context_radius": 1,
  "semantic": true,
  "generate": true
}
```

Response modes:

- `ollama_closed_corpus` — validated generated response
- `evidence_only` — model synthesis deliberately disabled
- `extractive_fallback` — Ollama unavailable; Scripture evidence only
- `rejected_model_output` — model violated JSON/citation contract
- `no_evidence` — retrieval found nothing useful

## Tests

```bash
pytest
```

The test suite covers reference parsing, exact and lexical retrieval, USFM ingestion, citation rejection, and extractive fallback.

## Suggested next layers

Keep future evidence classes physically separate rather than mixing them into the Scripture database:

1. Scripture translations
2. Hebrew/Aramaic/Greek + morphology
3. Second Temple / ANE historical corpora
4. Commentary or scholarship

A future UI can then allow explicit evidence-tier selection while preserving provenance.
