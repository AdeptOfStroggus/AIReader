# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                  # Install dependencies
uv run main.py           # Launch GUI
pytest                   # Run tests
flake8 . --count --select=E9,F63,F7,F82          # Strict lint (errors only)
flake8 . --count --exit-zero --max-line-length=127  # Full lint (non-blocking)
```

**Environment:** Copy `.env.example` to `.env` and set:
- `OPENAI_API_KEY` — Together AI API key (format: `tgp_v1_...`)
- `OPENAI_BASE_PATH` — `https://api.together.xyz/v1`

Python 3.11–3.12 required (3.13+ not supported). Use `uv`, not pip.

## Architecture

AIReader is a desktop PDF reader with AI-powered chat, built on PySide6 + Together AI.

### GUI Layer (`ui/`)
- `ui/ui.py` — `MainApp` (QMainWindow): top-level window, menu bar, theme, panel layout
- `ui/readerPanel.py` — `ReaderPanel`: QPdfView for rendering + converted text display; spawns `GpuWorker` (QThread) for off-thread PDF conversion
- `ui/aiAssistant_ui.py` — `AIAssistantPanel`: chat bubble UI, model selector, reset button

### AI Layer (`ai_client.py`)
Three classes, each with a distinct responsibility:
- `ImageIndexer` — converts page images to CLIP embeddings, stores in FAISS, retrieves by semantic similarity
- `RAGManager` — splits text into chunks, embeds with sentence-transformers, stores in FAISS; uses LLM-generated multi-query expansion for retrieval
- `AIClient` — Together AI API client (AsyncOpenAI-compatible); orchestrates RAG + image search, manages chat history, formats source citations as HTML links with page numbers

### Document Processing (`doc_converter.py`)
- `Converter` class lazy-loads Docling on first use
- GPU-accelerated (CUDA) with CPU fallback; batch sizes: `page_batch_size=32`, `ocr_batch_size=32`
- EasyOCR handles scanned pages (Russian + English)

### Data Flow
1. PDF loaded → `ReaderPanel` renders via QPdfView
2. `GpuWorker` converts pages via Docling/OCR in background
3. Converted text/images → `RAGManager` + `ImageIndexer` build FAISS indices
4. User question → multi-query RAG + image search → Together AI generates answer with clickable page-number citations

## Key Notes

- Together AI distinguishes **serverless** vs **dedicated** model endpoints — see `serverless-models.md` for the model catalog; `AIClient` filters models accordingly
- `QThreadPool` parallelizes image indexing; `QMutex` guards shared state
- Chat history is maintained in `AIClient` and reset via the UI reset button
