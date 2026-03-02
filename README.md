# ARES — Autonomous Diagnostic Engine for Maritime Fleet Reliability

ARES is a multi-agent AI system for diagnosing maritime equipment faults. It ingests your vessel's technical manuals and SOPs into a semantic knowledge base, then reasons over them using a chain of specialist AI agents to produce a validated diagnostic report — with every claim traced back to a specific page in your own documentation.

Built by a former Marine Engineer Officer.

---

## The Problem

When equipment fails at sea, an engineer must search through hundreds of pages of manuals under time pressure to find the right procedure. A 600-page engine manual, a stack of SOPs, troubleshooting guides — cross-referencing all of them manually takes hours. Errors in that process cost time, money, and in critical faults, safety.

## What ARES Does

ARES reduces that to minutes. Describe the fault in plain language. ARES searches the indexed manuals, reasons over the relevant passages, and returns a structured diagnostic report:

```
FAULT SUMMARY:
  Purifier bowl vibrating excessively with throughput drop and back-pressure rise.

PROBABLE CAUSE:
  Sludge accumulation in bowl causing imbalance. Feed temperature below separation
  threshold resulting in incomplete separation and progressive clogging.
  [alcap.pdf, p.47] [alcap.pdf, p.63]

SEVERITY: MEDIUM
  Fault is stable but will escalate to bowl trip if sludge discharge interval
  is not reduced. No immediate propulsion risk.

CONFIDENCE: 0.88

IMMEDIATE ACTIONS:
  1. Reduce throughput to 60% rated flow [alcap.pdf, p.47]
  2. Verify feed temperature is within 90–98°C [alcap.pdf, p.31]
  3. Initiate manual sludge discharge cycle [alcap.pdf, p.52]

REPAIR STEPS:
  1. Stop purifier and allow bowl to decelerate to rest [alcap.pdf, p.71]
  2. Open bowl hood and inspect disc stack for fouling [alcap.pdf, p.74]
  3. Clean disc stack with approved solvent per maintenance schedule [alcap.pdf, p.78]

SOP REFERENCES:
  - [alcap.pdf, p.47] — throughput reduction procedure for high vibration
  - [alcap.pdf, p.63] — feed temperature limits and effects on separation
  - [alcap.pdf, p.71] — bowl disassembly procedure

SAFETY NOTES:
  - Do not open bowl until spindle has fully stopped [alcap.pdf, p.70]

CONTRAINDICATIONS (do NOT perform):
  - Do not increase throughput — bowl imbalance will worsen
  - Do not bypass heater — cold fuel increases separation failure risk

VALIDATION STATUS: PASS
```

Every repair step in the output comes from a retrieved passage in the indexed manual — not from the model's general knowledge.

---

## Architecture

```
Fault Description
      │
      ▼
┌──────────────────┐
│  Researcher      │  Runs 3+ targeted vector searches on indexed manuals.
│  Agent           │  Retrieves relevant passages with source + page number.
└────────┬─────────┘
         │  Technical context report (cited)
         ▼
┌──────────────────┐
│  Analyst         │  Derives root cause, severity, and repair steps
│  Agent           │  exclusively from retrieved passages. No invented steps.
└────────┬─────────┘
         │  Failure analysis (cited)
         ▼
┌──────────────────┐
│  Validator       │  Checks all steps against safety_rules.yaml.
│  Agent           │  Strips any step that lacks a page citation.
└────────┬─────────┘
         │
         ▼
  Validated Diagnostic Report
```

---

## Features

- **Scanned and text PDFs** — OCR via Tesseract for scanned manuals; native text extraction for digital ones
- **Memory-efficient ingestion** — streams one page at a time; processes 600+ page manuals without memory issues
- **Citation-grounded output** — every repair step must cite the page it came from; uncited steps are stripped by the validator
- **Safety rules engine** — equipment limits, manufacturer interlocks, and contraindications defined in `safety_rules.yaml`
- **Severity derived from evidence** — CRITICAL / HIGH / MEDIUM / LOW assessed from fault context, not defaulted
- **Source verification mode** — `--cite` flag appends the raw retrieved passages after the report so engineers can verify claims in the physical manual
- **Direct knowledge search** — `ares search` queries the indexed documents without running the full diagnostic pipeline
- **10 equipment systems** — main engine, auxiliary engine, fuel oil purifier, purifier/clarifier, steering gear, pumps, HVAC, boilers, electrical, safety systems

---

## Getting Started

### Prerequisites

- Python 3.10+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (for scanned PDFs)
- OpenAI API key
- Qdrant Cloud account ([free tier](https://cloud.qdrant.io) — 1 GB)

### Install

```bash
# Clone the repository
git clone https://github.com/your-username/ares.git
cd ares

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install
pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
```

Edit `.env`:
```
OPENAI_API_KEY=sk-...
QDRANT_URL=https://your-instance.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-api-key
```

### Verify

```bash
ares health
```

```
Component          Status
OpenAI API         ✓ Connected
Qdrant Vector DB   ✓ Connected
Configuration      ✓ Loaded
```

### Ingest a Manual

```bash
ares ingest --path data/manuals/alcap.pdf \
            --equipment purifier_clarifier \
            --type manual
```

ARES streams through the PDF one page at a time — OCR-ing scanned pages, chunking the text, embedding it, and inserting it into Qdrant. Progress is shown per page.

### Run a Diagnostic

```bash
ares diagnose --fault "Purifier bowl vibrating heavily, throughput dropping" \
              --equipment purifier_clarifier
```

Add `--cite` to append the raw retrieved passages with exact page numbers:

```bash
ares diagnose --fault "Purifier bowl vibrating heavily" \
              --equipment purifier_clarifier \
              --cite
```

### Search the Knowledge Base Directly

```bash
ares search "bowl vibration alarm" --equipment purifier_clarifier
```

Returns a table showing page number, relevance score, source file, and a text excerpt for each result.

---

## Supported Equipment Systems

| `--equipment` value | Equipment |
|---------------------|-----------|
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

---

## Document Types

| `--type` value | Use for |
|----------------|---------|
| `manual` | Equipment manuals, operation and maintenance handbooks |
| `sop` | Standard Operating Procedures |
| `troubleshooting` | Fault-finding guides, diagnostic procedures |
| `safety_bulletin` | Safety alerts, manufacturer bulletins |
| `parts_catalog` | Spare parts lists, illustrated parts breakdowns |

---

## CLI Reference

```bash
ares ingest    --path <file|dir> --equipment <system> --type <doc_type>
ares diagnose  --fault "<description>" [--equipment <system>] [--cite]
ares search    "<query>" [--equipment <system>] [--limit N]
ares index                                # vector DB stats
ares health                               # API connection check
ares benchmark generate [--count N]       # generate synthetic fault scenarios
ares benchmark run                        # run benchmark suite
ares benchmark report                     # show accuracy metrics
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Multi-agent orchestration | [CrewAI](https://github.com/crewAIInc/crewAI) |
| Vector database | [Qdrant](https://qdrant.tech) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Reasoning agents | OpenAI `gpt-4o-mini` |
| Validation agent | OpenAI `gpt-4o` |
| PDF text extraction | pdfplumber |
| OCR | Tesseract via pdf2image + pytesseract |
| CLI | Typer + Rich |
| Configuration | Pydantic Settings |

---

## Project Structure

```
ares/
├── src/ares/
│   ├── cli.py                    # All CLI commands
│   ├── config/
│   │   ├── settings.py           # Environment config
│   │   ├── agents.yaml           # Agent definitions
│   │   └── tasks.yaml            # Task prompts and output format
│   ├── schemas/                  # Pydantic data models
│   ├── ingestion/                # PDF processing, chunking, embedding
│   ├── retrieval/                # Qdrant client
│   ├── safety/                   # Rules engine and validator
│   ├── agents/                   # CrewAI crew
│   └── benchmark/                # Scenario generator and runner
├── data/
│   ├── manuals/                  # Place your PDFs here
│   ├── safety_rules.yaml         # Equipment limits and interlocks
│   └── benchmarks/               # Scenarios and results
├── .env.example                  # Credential template
├── INSTALLATION.md               # Detailed setup guide
└── QUICK_REFERENCE.md            # Command cheat sheet
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `No module named 'ares'` | Run `pip install -e .` from the `ares/` directory |
| `OpenAI API: Invalid key` | Check `.env` — no extra spaces around the key |
| `Qdrant: Connection refused` | Verify `QDRANT_URL` and `QDRANT_API_KEY` in `.env` |
| `tesseract not found` | `brew install tesseract` (macOS) or `apt install tesseract-ocr` (Linux) |
| Diagnostic responses are generic | Not enough relevant documents indexed — ingest more manuals for that equipment |
| Process killed mid-ingestion | Reduce `EMBEDDING_BATCH_SIZE` in `.env` |

For a full setup walkthrough including Windows installation, see [INSTALLATION.md](INSTALLATION.md).

---

## License

MIT

---

*Version 1.0.0 — March 2026*
