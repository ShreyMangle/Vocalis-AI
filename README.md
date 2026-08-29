# Vocalis AI - Automated Voice Agent Platform

Vocalis AI is a full-stack, production-grade AI voice agent platform designed for small and medium businesses (dental clinics, wellness spas, salons, auto shops) to eliminate appointment no-shows. The platform automatically places outbound calls to confirm, reschedule, or cancel upcoming appointments—replacing rigid interactive voice response (IVR) phone trees with sub-second, natural spoken conversation.

To make local development and portfolio showcases friction-free, **this version runs entirely on free, developer-tier, or keyless API services** and includes a built-in **Web Sandbox Call Simulator** that streams bidirectional audio directly from your browser's microphone with a real-time neon spectrogram visualizer.

---

## 🚀 Key Features

* **Visual ROI Analytics & Business Value Simulator**:
  * Tracks confirmed, rescheduled, and cancelled appointments in real time.
  * Interactive booking value slider (`$50 - $500`) calculating custom annual recovered revenue and saved administrative hours.
* **Blazing Fast Conversational Speech Pipeline**:
  * **Speech-to-Text (STT)**: Utterance-based recording using a local RMS Voice Activity Detector (VAD) coupled with Groq's free Whisper-large-v3 API (sub-150ms transcription).
  * **LLM Orchestration**: Switches dynamically between Groq (Llama-3.1-70B), Google Gemini (1.5 Flash), Anthropic Claude 3.5 Sonnet, and a fallback rule engine, handling live database scheduling modifications via function calling.
  * **Text-to-Speech (TTS)**: Microsoft Edge Neural TTS voice integration—completely keyless, free, and ultra-natural with tunable speech rates (`-10%` to `+20%`).
* **Live iCalendar (RFC 5545) Sync Feed**:
  * Dedicated live URL subscription endpoint (`/api/calendar/{business_id}/feed.ics`) for Google Calendar, Apple Calendar, and Microsoft Outlook.
* **Batch Outbound Reminder Campaigns**:
  * One-click trigger or scheduled cron engine to dispatch 24h reminders across all pending appointments.
* **Call Intelligence & Sentiment Analysis**:
  * Automatic sentiment tagging (`Positive`, `Neutral`, `Urgent`, `Frustrated`) and intent extraction (`Confirmation`, `Reschedule`, `Cancellation`, `Human Escalation`).
  * Instant CSV analytics and call history report export (`/api/calls/export.csv`).
* **Web Voice Sandbox Simulator**:
  * Test the voice agent directly inside your browser! Downsamples microphone inputs to 16kHz PCM, streams via WebSockets, and plays synthesized Edge TTS MP3 frames natively.
  * Live neon audio spectrogram visualizer and downloadable call session audio (`.webm`).
* **Multi-stage Docker & PostgreSQL/Redis Support**:
  * Multi-stage production Dockerfiles with `docker-compose` stack configuring PostgreSQL 15, Redis 7, FastAPI, and Nginx.

---

## 📂 Project Architecture

```
/vocalis-ai
  ├── /backend                  # Python FastAPI WebSocket & REST Server
  │     ├── /app
  │     │     ├── __init__.py
  │     │     ├── audio_utils.py# G.711 µ-law transcoders & RMS VAD detector
  │     │     ├── auth.py       # JWT tokens & Bcrypt cryptography hashing
  │     │     ├── db.py         # DB connector (SQLite fallback + PostgreSQL asyncpg)
  │     │     ├── main.py       # FastAPI router endpoints & HTTP Server
  │     │     ├── pipeline.py   # WebSockets pipeline (STT ↔ LLM ↔ TTS)
  │     │     └── redis_client.py # Redis session store & Pub/Sub event dispatcher
  │     ├── /tests              # Pytest automated test suite
  │     │     ├── test_api.py   # Asynchronous API integration test lifecycle
  │     │     ├── test_audio.py # Audio transcoder & VAD state machine tests
  │     │     └── test_auth.py  # Authentication and JWT decoding tests
  │     ├── Dockerfile          # Backend container image
  │     ├── requirements.txt    # Python dependencies (FastAPI, Edge-TTS, Twilio, Redis)
  │     └── pytest.ini          # Asyncio test configuration
  │
  ├── /frontend                 # Vite React + Tailwind CSS v4 Dashboard
  │     ├── /src
  │     │     ├── /pages
  │     │     │     ├── Appointments.jsx  # Appointments manager, iCal sync & batch dispatcher
  │     │     │     ├── Billing.jsx       # Pricing tiers, annual discount toggle & checkout
  │     │     │     ├── CallLogs.jsx      # Conversation transcripts, sentiment & CSV exporter
  │     │     │     ├── Dashboard.jsx     # Recharts, ROI slider & latency telemetry
  │     │     │     ├── Login.jsx         # Authentication portal
  │     │     │     ├── Sandbox.jsx       # Web voice simulator & spectrogram visualizer
  │     │     │     └── Settings.jsx      # Persona tuning, voice preview & VAD controls
  │     │     ├── App.jsx       # Layout, navigation tabs & user state
  │     │     └── index.css     # Glassmorphic cyber theme styles
  │     ├── Dockerfile          # Multi-stage Nginx container image
  │     ├── package.json        # Frontend scripts and Lucide icons
  │     └── vite.config.ts      # Bundler config
  │
  ├── docker-compose.yml        # PostgreSQL 15, Redis 7, Backend & Frontend stack
  ├── PRODUCT_SPEC.md           # Product & SaaS Specification
  └── README.md                 # Project handbook
```

---

## 🛠️ Installation & Setup

### Prerequisites
* **Python 3.10+** (Verify with `python --version`)
* **Node.js 18+** & **npm** (Verify with `node -v` and `npm -v`)

---

### Step 1: Configure Environment Keys
Navigate to `/backend` and create a `.env` file (you can copy `.env.example` as a template):

```bash
cd backend
cp .env.example .env
```

Open `.env` and fill in your keys:
```env
# Required for Llama-3.1 Brain and Whisper Speech-to-Text (Completely Free)
GROQ_API_KEY=gsk_...

# Optional - alternative LLMs
GEMINI_API_KEY=
XAI_API_KEY=
ANTHROPIC_API_KEY=

# Optional - for real phone calls
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
```
*Note: If no API keys are provided, the server operates in a zero-downtime simulated mock mode, letting you experience the full system visually.*

---

### Step 2: Install Backend Packages & Run Tests
Install Python dependencies:

```bash
cd backend
pip install -r requirements.txt
```

Run the automated test suite:
```bash
pytest -v
```

---

### Step 3: Install Frontend Packages
Navigate to `/frontend` and install package dependencies:

```bash
cd ../frontend
npm install
```

---

## 🚦 How to Run the App

You will need to open two terminal windows (one for the backend, one for the frontend):

### 1. Launch Backend Server
In the `/backend` folder:
```bash
cd backend
uvicorn app.main:app --port 5000 --reload
```
*The server boots on `http://localhost:5000`, auto-bootstrapping `backend/data/database.sqlite`.*

### 2. Launch Frontend Client
In the `/frontend` folder:
```bash
cd frontend
npm run dev
```
*Open `http://localhost:5173` in your browser.*

---

## 🎯 How to Test it (Voice Sandbox)

1. Register an account or sign in on the Login screen.
2. Navigate to **Appointments** and add an appointment (e.g. name: `Alice`, phone: `+1555123456`, time: tomorrow).
3. Navigate to **Live Sandbox**.
4. Select `Alice` from the dropdown list.
5. Choose your input mode:
   * **Voice Mode**: Speak into your microphone. The VAD and spectrogram visualizer will track your voice in real time.
   * **Text Mode (Fallback)**: Type responses in the console input bar and press enter.
6. Click **Start Simulated Call**.
7. The AI virtual assistant will say the greeting. Converse with it to confirm, cancel, or reschedule.
8. Hang up and click **Download Session Recording** or inspect **Call History** to see conversation transcripts, sentiment analysis, and latency breakdowns!
