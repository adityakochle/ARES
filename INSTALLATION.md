# ARES Installation & Setup Guide

## 📋 Prerequisites

- **Python:** 3.10 or higher
- **System Dependencies:** Tesseract OCR (for scanned PDFs)
- **API Keys:**
  - OpenAI API key (for embeddings and LLM)
  - Qdrant Cloud account (free tier available)

## 🚀 Installation Steps

### 1. Install System Dependencies

#### macOS
```bash
brew install tesseract
```

#### Ubuntu/Debian
```bash
sudo apt-get install tesseract-ocr
```

#### Windows
Download from: https://github.com/UB-Mannheim/tesseract/wiki

### 2. Set Up Python Environment

```bash
# Navigate to ARES directory
cd /Users/adityakochle/ARES/ares

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
# Install project in development mode with all dependencies
pip install -e ".[dev]"

# Verify installation
pip list | grep -E "crewai|pydantic|qdrant|openai|typer"
```

### 4. Configure Environment Variables

```bash
# Copy template
cp .env.example .env

# Edit .env with your credentials
nano .env
# OR
# open -a "Visual Studio Code" .env
```

**Required Environment Variables:**
```
OPENAI_API_KEY=sk-your-openai-api-key
QDRANT_URL=https://your-instance.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-api-key
```

### 5. Verify Installation

```bash
# Check system health
ares health

# Expected output:
# Component Status
# OpenAI API     ✓ Connected
# Qdrant Vector DB  ✓ Connected
# Configuration  ✓ Loaded
```

## 🧪 Quick Test

### Test 1: Check Vector Database
```bash
ares index
```

### Test 2: Ingest Sample Document
First, add a PDF to `data/manuals/`:
```bash
ares ingest --path data/manuals/sample.pdf \
            --equipment main_engine \
            --type manual
```

### Test 3: Run Diagnostics
```bash
ares diagnose --fault "High temperature on bearing, 85°C"
```

## 📁 Project Structure After Setup

```
ares/
├── .env                    # Your configuration (gitignored)
├── venv/                   # Virtual environment (gitignored)
├── src/ares/               # Source code (ready to use)
├── data/
│   ├── manuals/           # Add your PDFs here
│   ├── safety_rules.yaml  # Equipment specifications
│   └── benchmarks/        # Benchmark results
├── README.md              # Quick start guide
├── BUILD_SUMMARY.md       # Build completion report
└── .github/copilot-instructions.md  # AI agent guidance
```

## 🔑 Obtaining Required Credentials

### OpenAI API Key
1. Go to https://platform.openai.com/account/api-keys
2. Create new secret key
3. Copy and paste into `.env` as `OPENAI_API_KEY`

### Qdrant Cloud Account
1. Go to https://cloud.qdrant.io
2. Sign up for free account (1GB free tier)
3. Create a new cluster
4. Copy URL and API key into `.env` as:
   - `QDRANT_URL`
   - `QDRANT_API_KEY`

## 🐛 Troubleshooting

### Issue: "No module named 'ares'"
**Solution:** Make sure you ran `pip install -e .` from the ares directory

### Issue: "OpenAI API Error: Invalid API key"
**Solution:** 
1. Check `.env` file exists
2. Verify `OPENAI_API_KEY` is set correctly
3. Confirm key has no extra spaces

### Issue: "Qdrant Connection refused"
**Solution:**
1. Check `QDRANT_URL` format
2. Verify `QDRANT_API_KEY` is correct
3. Test connectivity: `ping your-instance.qdrant.io`

### Issue: "Command 'tesseract' not found"
**Solution:**
1. Reinstall tesseract (see System Dependencies)
2. Restart terminal
3. Verify: `which tesseract`

### Issue: "No such file or directory: 'data/safety_rules.yaml'"
**Solution:** Ensure you're running commands from the ares directory

## 📚 Next Steps

1. **Upload Documents:** Add maritime PDFs to `data/manuals/`
2. **Test Ingestion:** Run `ares ingest --path data/manuals/`
3. **Verify Index:** Run `ares index` to check vector DB
4. **Run Diagnostics:** Test with `ares diagnose --fault "..."`
5. **Benchmark:** Run `ares benchmark generate && ares benchmark run`

## 📖 Additional Resources

- **README.md** - Project overview
- **BUILD_SUMMARY.md** - Complete build report
- **.github/copilot-instructions.md** - Developer guide
- **pyproject.toml** - Project configuration

## 💬 Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review `.github/copilot-instructions.md`
3. Check CLI help: `ares --help`

---

**Installation Date:** February 13, 2026  
**Status:** ✅ Ready for use
