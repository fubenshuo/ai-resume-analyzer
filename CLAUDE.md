# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI 赋能的智能简历分析系统 — AI-powered resume parsing and job matching system. Users upload PDF resumes; the system extracts structured information (name, contact, education, skills, projects) via LLM and computes a multi-dimensional match score against a job description.

## Development Commands

```bash
# Backend — install dependencies
cd backend && pip install -r requirements.txt

# Backend — start dev server (with auto-reload)
cd backend && python main.py
# or: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Backend — API docs (Swagger)
# Open http://localhost:8000/docs after starting the server

# Frontend — local dev server
cd frontend && python -m http.server 3000
# Open http://localhost:3000
```

## Architecture

```
frontend (vanilla HTML/CSS/JS)  ──HTTP──▶  FastAPI backend
                                              ├── pdf_parser.py     (pdfplumber)
                                              ├── text_processor.py (regex cleaning + sectioning)
                                              ├── info_extractor.py (LLM primary, regex fallback)
                                              ├── matcher.py        (LLM primary, keyword fallback)
                                              ├── cache.py          (memory dict | Redis)
                                              ├── config.py         (pydantic-settings, env vars)
                                              └── models.py         (Pydantic models)
```

### Key Design Decisions

- **AI-first with rule-based fallback**: `info_extractor.py` and `matcher.py` both try the LLM API first and fall back to regex/keyword matching on failure. This means the system works even without an API key configured, though with reduced accuracy.
- **LLM API is OpenAI-compatible**: Configurable via `AI_API_BASE_URL` + `AI_API_KEY` + `AI_MODEL` env vars — works with Qwen (通义千问), DeepSeek, GPT, or any OpenAI-compatible endpoint.
- **Caching keyed on content hash**: `cache.make_key("resume:analysis", SHA256(cleaned_text + JD))` deduplicates identical analyses. Memory cache by default; set `CACHE_TYPE=redis` for multi-instance deployments.
- **In-memory file store**: Uploaded resume texts live in a Python dict (`_uploaded_files` in `main.py`). For production/Alibaba Cloud FC, swap this for OSS or a database.

### API Flow

1. `POST /api/upload` → parse PDF, clean text, store in memory, return `resume_id`
2. `POST /api/analyze/{resume_id}` with `{job_description}` → extract info + match → return full `AnalyzeResponse`
3. `GET /api/health` → liveness check

### Scoring Formula (rule-based fallback)

```
overall_score = skill_match_rate × 50 + experience_relevance × 25 + education_match × 25
```

All three sub-scores are in [0, 1]; `overall_score` is [0, 100].

### Frontend Note

The frontend's `API_BASE` is hardcoded in `frontend/app.js` — change it before deploying to GitHub Pages to point to the actual backend URL.
