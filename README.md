# 🎙️ VoxAI — AI Voice Operations Platform

<div align="center">

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python_3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis_7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![React](https://img.shields.io/badge/React_19-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev)

**A production-grade AI Voice SaaS platform that lets businesses deploy AI receptionists to handle phone calls automatically.**

</div>

---

## 📖 What is VoxAI?

VoxAI allows businesses (clinics, hotels, restaurants, salons) to create AI voice agents that answer customer phone calls, understand intent, check availability, book appointments, and escalate to humans when needed — all with sub-second response latency.

> **Current Status:** Week 1 — Foundation  
> Old prototype preserved on branch: `archive/v1-monolith`

---

## 🏗️ Architecture

```
Customer → Phone Call → VoBiz/Twilio → WebSocket → FastAPI Backend
                                                         │
                                              ┌──────────┼──────────┐
                                           Deepgram    GPT-4o    Cartesia
                                            (STT)     (LLM)      (TTS)
                                                         │
                                              ┌──────────┼──────────┐
                                           PostgreSQL  Redis       S3
                                           + pgvector
```

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Docker Desktop installed and running
- Git

### 1. Clone and configure
```bash
git clone https://github.com/ShreyMangle/Vocalis-AI.git
cd Vocalis-AI

# Create backend .env from example
cp backend/.env.example backend/.env
# Edit backend/.env — at minimum set your GROQ_API_KEY for free LLM access
```

### 2. Start everything
```bash
docker-compose up
```

This starts:
| Service | URL | What it is |
|---|---|---|
| **Frontend** | http://localhost:5173 | React dashboard |
| **Backend API** | http://localhost:8000 | FastAPI server |
| **API Docs** | http://localhost:8000/docs | Auto-generated Swagger UI |
| **Health** | http://localhost:8000/health | Server health check |
| **PostgreSQL** | localhost:5432 | Database |
| **Redis** | localhost:6379 | Cache |

### 3. Verify
```bash
curl http://localhost:8000/health
# → {"status":"ok","app":"VoxAI","version":"0.1.0","environment":"development"}
```

---

## 📁 Project Structure

```
VoxAI/
├── backend/
│   ├── app/
│   │   ├── core/           ← Config, logging, exceptions
│   │   ├── api/v1/         ← Route handlers (added week by week)
│   │   ├── models/         ← SQLAlchemy DB models
│   │   ├── schemas/        ← Pydantic request/response schemas
│   │   ├── services/       ← Business logic
│   │   ├── repositories/   ← Database access
│   │   ├── ai/             ← LLM, STT, TTS, RAG, tools
│   │   ├── voice/          ← WebSocket voice pipeline
│   │   └── main.py         ← FastAPI app entry point
│   ├── alembic/            ← Database migrations
│   ├── tests/              ← Unit + integration tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/                ← React + TypeScript source
│   └── Dockerfile
├── scripts/
│   └── init-db.sql         ← DB initialization (pgvector setup)
├── docker-compose.yml      ← Local dev stack
└── README.md
```

---

## 🗓️ Development Roadmap

| Week | Focus | Status |
|---|---|---|
| **Week 1** | Architecture + Docker + Health endpoints | ✅ Complete (8 tests) |
| **Week 2** | Multi-tenancy + Authentication (JWT, RBAC) | ✅ Complete (57 tests) |
| **Week 3** | Business onboarding (profile, hours, services) | ✅ Complete (92 tests) |
| **Week 4** | Agent configuration + LLM provider abstraction | ✅ Complete (105 tests) |
| **Week 5** | RAG knowledge base (pgvector, documents, FAQs, semantic search) | ✅ Complete (15 tests) |
| **Week 6** | AI Orchestrator + Function Tool calling | ✅ Complete (7 tests) |
| **Week 7** | Appointment system (slots, booking, conflicts, iCal) | ✅ Complete (113 tests) |
| **Week 8** | Voice pipeline (audio G.711 mulaw, VAD, barge-in, STT, TTS) | ✅ Complete (15 tests) |
| **Week 9** | Telephony integration (VoBiz India primary + Twilio global fallback) | ✅ Complete (122 tests) |
| **Week 10** | Cost tracking + Analytics + CSV export | ✅ Complete (128 tests) |
| **Week 11** | Modern Frontend dashboard (React 19, TypeScript, Vite, Tailwind 4) | ✅ Complete (Full SaaS UI) |
| **Week 12** | Production security hardening + Container deployment | 🔜 Final Verification |

---

## 🛠️ Technology Stack

| Layer | Technology | Why |
|---|---|---|
| Backend | Python 3.12 + FastAPI | Async-first, auto-docs, type-safe |
| Database | PostgreSQL 16 + pgvector | Relational + vector search in one DB |
| Cache | Redis 7 | Sub-millisecond session state |
| Frontend | React 19 + TypeScript + Vite | Fast, type-safe, modern |
| STT | Deepgram Nova-3 | ~200ms streaming latency |
| TTS | Cartesia Sonic | ~40ms first-audio latency |
| LLM | OpenAI GPT-4o-mini (default) | Best tool-calling, cost-effective |
| Telephony | VoBiz (India) / Twilio (Global) | TRAI-compliant for India |
| Storage | AWS S3 | Industry standard file storage |
| Container | Docker + Docker Compose | Environment consistency |

---

## 🧪 Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE)
