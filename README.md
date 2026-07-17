# Vocalis AI - Automated Voice Agent Platform

Vocalis AI is a full-stack, open-source AI voice agent platform designed for small businesses (dental clinics, salons, auto shops) to reduce appointment no-shows. The platform automatically places outbound calls to confirm, reschedule, or cancel upcoming appointments—replacing rigid phone trees with a real-time, natural spoken conversation.

To make local development and portfolio showcases friction-free, **this version runs entirely on free, developer-tier, or keyless API services** and includes a built-in **Web Sandbox Call Simulator** that streams audio directly from your browser's microphone.

---

## 🚀 Key Features

* **Visual ROI Analytics Dashboard**: Tracks confirmed, rescheduled, and cancelled appointments. Estimates "No-shows prevented" and "Recovered revenue" based on custom appointment values.
* **Blazing Fast Conversational Speech Pipeline**:
  * **Speech-to-Text (STT)**: Utterance-based recording using a local RMS Voice Activity Detector (VAD) coupled with Groq's free Whisper-large-v3 API (sub-150ms transcription).
  * **LLM Orchestration**: Switches dynamically between Groq (Llama-3.1-70B), Google Gemini (1.5 Flash), xAI Grok, or Claude, handling live database scheduling modifications via function calling.
  * **Text-to-Speech (TTS)**: Microsoft Edge Neural TTS voice integration—completely keyless, free, and premium-sounding.
* **Web Sandbox Simulator**: Test the voice agent directly inside your browser! Connects via WebSockets, downsamples microphone inputs to 16kHz PCM, streams it, and decodes Edge TTS MP3 frames natively in the browser.
* **CSV Bulk Importer**: paste appointment lists directly into the dashboard.
* **Zero-Config Database**: Auto-bootstraps a local SQLite database by default, with PostgreSQL support available via a single configuration.
* **Stripe Test Mode Billing**: Pricing plans table with Stripe checkout lifecycle hooks.

---

## 📂 Project Architecture

```
/hehe
  ├── /backend                  # Python FastAPI WebSocket Server
  │     ├── /app
  │     │     ├── __init__.py
  │     │     ├── auth.py       # JWT tokens & Cryptography hashing
  │     │     ├── db.py         # DB connector with SQLite auto-migrations
  │     │     ├── main.py       # FastAPI router endpoints & HTTP Server
  │     │     └── pipeline.py   # WebSockets pipeline (STT ↔ LLM ↔ TTS)
  │     ├── requirements.txt    # Python dependencies (Groq, Edge-TTS, FastAPI)
  │     ├── test_pipeline.py    # Isolated pipeline validator script
  │     └── .env                # Server API key configurations
  │
  ├── /frontend                 # Vite React + Tailwind CSS v4 Dashboard
  │     ├── /src
  │     │     ├── /pages
  │     │     │     ├── Appointments.jsx  # Appointments lists and CSV loader
  │     │     │     ├── Billing.jsx       # Pricing tiers and checkout
  │     │     │     ├── Dashboard.jsx     # Recharts and recovered revenue calculators
  │     │     │     ├── CallLogs.jsx      # Historical transcripts drawer & latency stats
  │     │     │     ├── Login.jsx         # Access portals
  │     │     │     └── Sandbox.jsx       # Web voice simulator (mic + player)
  │     │     ├── App.jsx       # Sidebars layout and routing
  │     │     ├── index.css     # Tailwind v4 glassmorphic styles
  │     │     └── main.jsx      # DOM entry point
  │     ├── package.json        # Frontend scripts and assets libraries
  │     └── vite.config.js      # Bundler config containing Tailwind
  │
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

# Optional - for real phone calls
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
```
*Note: If no API keys are provided, the server will operate in a simulated mock mode, letting you experience the system visually.*

### 🔑 How to Obtain the API Keys

Here is where to register and how to get each key for the platform:

#### 1. Groq API Key (`GROQ_API_KEY`) — *Recommended & Free*
* **Purpose**: Runs Llama-3.1-70B for the conversation logic + Whisper-large-v3 for low-latency Speech-to-Text.
* **Cost**: **100% Free** (developer tier).
* **Link**: [Groq Console](https://console.groq.com/)
* **Steps**: Create an account, click **API Keys** in the sidebar, and click **Create API Key**.

#### 2. Google Gemini API Key (`GEMINI_API_KEY`) — *Free LLM Alternative*
* **Purpose**: Alternative free LLM brain option.
* **Cost**: **100% Free** (pay-as-you-go developer trial).
* **Link**: [Google AI Studio](https://aistudio.google.com/)
* **Steps**: Sign in with your Google Account and click **Get API Key** in the top left.

#### 3. xAI Grok Key (`XAI_API_KEY`)
* **Purpose**: Alternative Grok LLM brain option.
* **Cost**: Paid (trial credits occasionally offered).
* **Link**: [xAI Console](https://console.x.ai/)
* **Steps**: Register, create an API key, and configure billing.

#### 4. Twilio Telephony Credentials — *For Real Phone Calls*
* **Purpose**: Placing outbound calls to actual cell phones.
* **Cost**: Free trial credit (~$15) upon registration, then pay-per-minute.
* **Link**: [Twilio Console](https://www.twilio.com/console)
* **Steps**:
  1. Copy the **Account SID** and **Auth Token** from the dashboard landing page.
  2. Click **Get a Trial Number** to claim an active caller phone number.

#### 5. Stripe Billing Keys — *For Subscriptions Demo*
* **Purpose**: Charging customers via Stripe Checkout sessions.
* **Cost**: **Free** in developer Test Mode.
* **Link**: [Stripe Dashboard](https://dashboard.stripe.com/)
* **Steps**: Enable **Test Mode** on the top right, navigate to **Developers -> API Keys**, and copy the **Publishable key** and **Secret key**.

---

### Step 2: Install Backend Packages
Install the Python dependencies:

```bash
cd backend
pip install -r requirements.txt
```

Verify that the backend initializes and logs test DB seeds successfully by running the pipeline validator:
```bash
python test_pipeline.py
```

---

### Step 3: Install Frontend Packages
Navigate to `/frontend` and install the package assets:

```bash
cd ../frontend
npm install
```

---

## 🚦 How to Run the App

You will need to open two terminal windows (one for the backend, one for the frontend):

### 1. Launch Backend Server
In the `/backend` folder, run the Uvicorn server:
```bash
cd backend
uvicorn app.main:app --port 5000 --reload
```
*The server will boot on `http://localhost:5000`, generating `backend/data/database.sqlite` automatically.*

### 2. Launch Frontend Client
In the `/frontend` folder, run the Vite development server:
```bash
cd frontend
npm run dev
```
*Open `http://localhost:5173` in your browser.*

---

## 🎯 How to Test it (Voice Sandbox)

1. Register a new business account on the Login screen.
2. Navigate to **Appointments** and add an appointment manually (e.g. name: `Bob`, phone: `+123456`, time: tomorrow).
3. Navigate to the **Live Sandbox** page.
4. Select `Bob` from the dropdown list.
5. Choose your input mode:
   * **Voice Mode**: Speak directly into your computer's microphone. The server VAD will detect when you stop talking and transcribe it.
   * **Text Mode (Fallback)**: Type your replies in the console input bar and press enter.
6. Click **Start Simulated Call**.
7. The AI virtual assistant will say the greeting. Converse with it to confirm, cancel, or reschedule.
8. Hang up and check **Call History** to see the turn-by-turn dialogue transcripts and sub-second latency analytics!
