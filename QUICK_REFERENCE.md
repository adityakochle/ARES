# ARES — Command Cheat Sheet

> Active session reference. For setup and architecture see [README.md](README.md).

---

## Session Start

```bash
cd /path/to/ares
source venv/bin/activate
ares health                          # verify API connections
ares index                           # check what's indexed
```

---

## Ingest

```bash
ares ingest -p <file_or_dir> -e <equipment> -t <doc_type>
```

| Flag | Short | Values |
|------|-------|--------|
| `--path` | `-p` | path to PDF file or directory |
| `--equipment` | `-e` | see table below |
| `--type` | `-t` | `manual` · `sop` · `troubleshooting` · `safety_bulletin` · `parts_catalog` |

**Equipment values**

| Value | Equipment |
|-------|-----------|
| `main_engine` | Main propulsion engine |
| `auxiliary_engine` | Generator / auxiliary engine |
| `fuel_oil_purifier` | Fuel oil purifier |
| `purifier_clarifier` | Clarifier / ALCAP system |
| `steering_gear` | Steering gear |
| `pumps_compressors` | Pumps and compressors |
| `hvac_refrigeration` | HVAC and refrigeration |
| `boilers` | Boilers |
| `electrical` | Electrical systems |
| `safety_systems` | Fire / safety detection |

**Examples**
```bash
ares ingest -p data/manuals/alcap.pdf -e purifier_clarifier -t manual
ares ingest -p data/manuals/ -e main_engine -t sop
```

---

## Search

```bash
ares search "<query>"
ares search "<query>" -e <equipment>
ares search "<query>" -e <equipment> -n <limit>   # default limit: 5
```

```bash
ares search "bowl vibration high"
ares search "lube oil pressure alarm" -e main_engine -n 10
```

---

## Diagnose

```bash
ares diagnose -f "<fault description>"
ares diagnose -f "<fault>" -e <equipment>         # focuses retrieval
ares diagnose -f "<fault>" -e <equipment> --cite  # appends raw evidence + page numbers
```

```bash
ares diagnose -f "Purifier bowl vibrating heavily, throughput dropping" \
              -e purifier_clarifier \
              --cite
```

---

## Database

```bash
ares index                           # collection stats (points, vector size)
```

---

## Benchmark

```bash
ares benchmark generate --count 150  # generate synthetic fault scenarios
ares benchmark run                   # run all scenarios
ares benchmark report                # show accuracy / timing metrics
```

---

## Help

```bash
ares --help
ares ingest --help
ares diagnose --help
ares search --help
```

---

## Environment Variables

**Required** (set in `.env`)
```
OPENAI_API_KEY=sk-...
QDRANT_URL=https://your-instance.qdrant.io:6333
QDRANT_API_KEY=...
```

**Optional** (shown with defaults)
```
LOG_LEVEL=INFO
EMBEDDING_MODEL=text-embedding-3-small
REASONING_MODEL=gpt-4o-mini
VALIDATION_MODEL=gpt-4o
QDRANT_COLLECTION=maritime_docs
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
EMBEDDING_BATCH_SIZE=32
SAFETY_RULES_PATH=data/safety_rules.yaml
```

---

## Key File Paths

```
data/manuals/                        ← place PDFs here before ingesting
data/safety_rules.yaml               ← equipment limits, interlocks, contraindications
src/ares/config/agents.yaml          ← agent roles and backstories
src/ares/config/tasks.yaml           ← task prompts and output format
.env                                 ← API credentials
```

---

## Common Errors

| Error | Fix |
|-------|-----|
| `No module named 'ares'` | `pip install -e .` from the `ares/` directory |
| `OpenAI API: Invalid key` | Check `.env` — no extra spaces |
| `Qdrant: Connection refused` | Verify `QDRANT_URL` and `QDRANT_API_KEY` |
| `tesseract not found` | `brew install tesseract` then restart terminal |
| Filtered search returns 0 results | Payload indexes missing — re-run ingest or call `ensure_payload_indexes()` |
