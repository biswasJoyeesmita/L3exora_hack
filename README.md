# LEXORA — Government Abuse & Threat Detection System 🛡️

**LEXORA** is an enterprise-grade, multi-stage Content Moderation, Threat Intelligence & Risk Assessment Pipeline built to monitor, classify, and analyze public discourse and social media commentary (e.g., YouTube video comments) surrounding government policies, public institutions, and sensitive civic events.

The system is architected to protect public safety and institutional integrity by identifying high-risk threats, incitement, and targeted abuse while rigorously safeguarding constitutional rights to lawful dissent, democratic criticism, and civic debate.

---

## 📑 Table of Contents

- [Key Highlights & Capabilities](#-key-highlights--capabilities)
- [System Architecture](#-system-architecture)
- [Granular Severity Tiers](#-granular-severity-tiers)
- [Core Execution Flows](#-core-execution-flows)
- [Repository & File Directory Guide](#-repository--file-directory-guide)
- [Cryptographic Audit Trail System](#-cryptographic-audit-trail-system)
- [API Reference](#-api-reference)
- [Installation & Getting Started](#-installation--getting-started)
- [Environment Configuration](#-environment-configuration)
- [Testing & Quality Assurance](#-testing--quality-assurance)
- [Target & Project Status](#-target--project-status)
- [License](#-license)

---

## ✨ Key Highlights & Capabilities

- **Dual-Server Hybrid Architecture:** Node.js/Express (`:3000`) serves the frontend web interface, security middleware, and API gateway, while a Python/Flask engine (`:5000`) executes ML classification, LLM reasoning, YouTube data ingestion, and cryptographic hashing.
- **Video-Centric Deep Ingestion:** Fetches real public commentary across configurable video depths (10 to 100+ videos) using the YouTube Data API v3, extracting video titles, captions, and context.
- **2-Stage Hybrid Classifier with Auto-Failover:**
  - **Fast Regex Pre-Filter (`lexicon.py`):** High-speed rule-based screen for abusive terms, incitement, threats, and government target entities. Clean/neutral comments bypass heavy LLM calls, slashing API costs and latency by 70–90%.
  - **Stage 1 & 2 LLM Contextual Classifier (`classify.py`):** Powered by Google Gemini (`gemini-3.6-flash`), performing sentence-level semantic intent analysis and extracting concrete trigger phrases with structured justifications.
  - **Auto-Failover Circuit Breaker (`classify_router.py`):** Automatically routes to a local offline Hugging Face RoBERTa transformer (`cardiffnlp/twitter-roberta-base-sentiment-latest`) during Gemini quota limits or network outages, with automatic 5-minute recovery.
- **Over-Flagging Normalization:** Strict `normalize_tier_decision()` enforcement prevents ordinary negative sentiment or passionate political frustration from being falsely classified as abusive (Tier 2+).
- **Tamper-Evident SHA-256 Audit Trail:** High-severity findings (Tier 3 Incitement and Tier 4 Threats) are appended to a cryptographic hash chain in `audit-log/tier_audit_chain.jsonl`. Real-time verification proves non-repudiation and detects data tampering or reordering.
- **Production Resilience & Security:** In-memory query caching (30-minute TTL), serialized heavy pipeline mutex locks (`_pipeline_lock`), Express rate limiting, Helmet Content Security Policies, and shared-secret API key protection (`LEXORA_API_KEY`).

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     LEXORA PLATFORM ARCHITECTURE                                 │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                FRONTEND DASHBOARD (public/)                              │   │
│   │   • index.html (Live Single Comment Demo & Audit Verification Panel)                    │   │
│   │   • analysis.html (Deep YouTube Topic & Video Scan Analytics Dashboard)                  │   │
│   │   • audit-trail.html (Cryptographic Evidence Inspector) & about.html (Team Info)        │   │
│   └─────────────────────────────────────────────┬────────────────────────────────────────────┘   │
│                                                 │ HTTP Requests (JSON / Static)                  │
│                                                 ▼                                                │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                             EXPRESS GATEWAY (:3000, server.js)                           │   │
│   │   • Helmet Security Headers & CORS        • Rate Limiters (/api/analyze, /api/contact)   │   │
│   │   • Python Auto-Spawner / Health Poller   • API Key Verification (requireApiKey.js)      │   │
│   │   • Routes: /api/analyze, /api/report, /api/audit, /api/contact                          │   │
│   └─────────────────────────────────────────────┬────────────────────────────────────────────┘   │
│                                                 │ Proxy Forwarding (Internal Key)                │
│                                                 ▼                                                │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                          FLASK ML & PIPELINE SERVER (:5000, api_server.py)               │   │
│   │   • 30-min In-Memory LRU Query Cache      • Mutex Pipeline Lock (_pipeline_lock)         │   │
│   │   • assess_risk() Risk Engine             • 4-Sentence Qualitative Topic Summary Builder │   │
│   └──────┬──────────────────────────────────────┬────────────────────────────────────┬───────┘   │
│          │                                      │                                    │           │
│          ▼                                      ▼                                    ▼           │
│   ┌───────────────┐                   ┌────────────────────┐               ┌─────────────────┐   │
│   │ YOUTUBE DATA  │                   │  CLASSIFICATION    │               │  TAMPER-EVIDENT │   │
│   │   INGESTION   │                   │      ROUTER        │               │   AUDIT LOG     │   │
│   │ youtube_      │                   │ classify_router.py │               │  audit_log.py   │   │
│   │ ingest.py     │                   └─────────┬──────────┘               └────────┬────────┘   │
│   └──────┬────────┘                             │                                   │            │
│          │ Fetches Comments                     │ Routes Traffic                    │ Tier 3 & 4 │
│          │ & Video Context                      ▼                                   │ Evidence   │
│          │                      ┌───────────────────────────────┐                   │ Logged     │
│          │                      │    lexicon.py (Fast Regex)    │                   ▼            │
│          │                      │  • Target & Threat Patterns   │          ┌─────────────────┐   │
│          │                      └──────┬─────────────────┬──────┘          │ SHA-256 JSONL   │   │
│          │                             │ Candidates      │ Clean (Tier 1)  │ Hash Chain Log  │   │
│          │                             ▼                 ▼                 │ tier_audit_     │   │
│          │                     ┌───────────────┐  [Instant Tier 1]         │ chain.jsonl     │   │
│          │       Primary (LLM) │  classify.py  │                           └─────────────────┘   │
│          │      ┌──────────────┤ (Gemini 3.6   │                                                 │
│          │      │              │  Flash API)   │                                                 │
│          │      │              └───────┬───────┘                                                 │
│          │      │ 503 / Failover       │ Normalized Tiers & Justifications                       │
│          │      ▼                      ▼                                                         │
│          │ ┌───────────────────────────────────┐                                                 │
│          │ │        classify_local.py          │                                                 │
│          │ │ (Hugging Face RoBERTa Transformer)│                                                 │
│          │ └───────────────────────────────────┘                                                 │
│          │                                                                                       │
│          ▼                                                                                       │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                             AGGREGATED REPORT & EVIDENCE OUTPUT                          │   │
│   │   • Tier Distributions (1-4)    • Risk Level (Low/Mod/High)   • AI Impact Summary        │   │
│   │   • Flagged Comments & Reasons  • Cached to model-output/     • Human Review Queue Ready │   │
│   └──────────────────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Granular Severity Tiers

Lexora categorizes every analyzed comment into four clear operational tiers:

| Tier | Category / Label | Description & Context | System Action |
| :--- | :--- | :--- | :--- |
| **Tier 1** | **Lawful / Neutral Criticism** | Legitimate political dissent, policy debate, venting frustration, emotional anger, or supportive discussion without targeted abuse or threats. | **Allowed / Passed** (No moderation action required) |
| **Tier 2** | **Abusive / Disrespectful** | Targeted harassment, derogatory slurs, profanity, or defamatory personal insults aimed at public officials or individuals. | **Queued for Review** (Sent to human moderation queue) |
| **Tier 3** | **Hate Speech / Incitement** | Content promoting communal hostility, calls for civil unrest, riots, severe hate speech, or illicit deception/scams. | **Priority Queued & Audit Logged** (Cryptographic evidence saved) |
| **Tier 4** | **Direct Threat / Exploit** | Explicit physical violence, assassination threats, anti-national sabotage, or prohibited cyber/AI exploits. | **Critical Priority & Audit Logged** (Immediate flag & tamper-evident record) |

---

## 🔄 Core Execution Flows

### 1. Live Single-Comment Demo Flow (`index.html`)
1. User enters a test comment in the UI widget.
2. `script.js` sends `POST /api/analyze` to Express (`:3000`).
3. Express calls `analyzeContent()` in `src/analyze.js`, which sends `POST /api/classify-text` to Flask (`:5000`).
4. `api_server.py` delegates to `classify_router.py` → `lexicon.py` → `classify.py` (Gemini 3.6 Flash).
5. If classified as Tier 3 or 4, `_audit_if_severe()` appends a record to the SHA-256 audit chain.
6. If the Python service is offline, Express automatically falls back to `src/data/lexicon.js`.

### 2. Full Topic Report & Deep Video Scan Flow (`analysis.html`)
1. User selects a topic/hashtag (e.g., `"Farm Bill 2026"`) and scan depth (10–100 videos).
2. `analysis.js` triggers `GET /api/report?query=...&target_videos=...` on Express.
3. Express forwards to Flask `POST /api/generate_report`.
4. Flask acquires `_pipeline_lock` and checks the 30-minute in-memory cache (`_cache`).
5. `youtube_ingest.py` queries YouTube Data API v3, extracts videos, captions, and comments.
6. Comments are pre-filtered via `lexicon.py`. Only candidate threats/abuse are sent to LLM `classify_batch()`.
7. `assess_risk()` computes risk level; Gemini synthesizes a 4-sentence qualitative community impact summary.
8. Structured JSON is returned, cached in `model-output/youtube_feed_report.txt.json`, and displayed on the dashboard.

### 3. Cryptographic Audit Chain Verification Flow (`audit-trail.html` / `index.html`)
1. User clicks **"Verify Audit Trail"** on the dashboard.
2. Browser hits `GET /api/audit/verify`.
3. `audit_log.py:verify_chain()` reads `audit-log/tier_audit_chain.jsonl`, recalculating every SHA-256 hash sequentially from the genesis block (`0000...`).
4. If valid: returns `{ "valid": true, "total_entries": N, "verified_through_hash": "..." }`.
5. If tampered/edited: returns `{ "valid": false, "broken_at_index": i, "reason": "..." }`, pinpointing the exact modified record.

---

## 📁 Repository & File Directory Guide

```
Government-Abuse-Detection-System/
└── Lexora/
    ├── brain/                                 ← Permanent architectural memory & decision records
    │   ├── ARCHITECTURE.md                    ← System architecture & structural overview
    │   ├── CONSTRAINTS.md                     ← Inviolable moderation safety & code rules
    │   ├── DECISIONS.md                       ← Living chronological architectural decision log
    │   ├── FLOW.md                            ← Line-by-line runtime execution traces
    │   ├── HANDOVER.md                        ← Session state, handoffs, and known rough edges
    │   ├── ROLLBACK.md                        ← Emergency rollback guides and safe checkpoints
    │   ├── TEST_CHECKLIST.md                  ← Pre-flight & release manual verification checklist
    │   └── VERSION_LOG.md                     ← Per-session changelog
    │
    └── L3exora_hack/                           ← MAIN WORKING REPOSITORY ROOT
        ├── server.js                          ← Express server entrypoint (:3000) with Python process auto-spawning
        ├── api_server.py                      ← Flask API service (:5000), pipeline orchestration & risk assessment
        ├── classify.py                        ← Gemini 3.6 Flash 2-stage classifier with retry & tier normalization
        ├── classify_local.py                  ← Offline Hugging Face RoBERTa transformer & video sentiment engine
        ├── classify_router.py                 ← Thread-safe failover circuit breaker (Gemini ↔ RoBERTa)
        ├── lexicon.py                         ← Regex pattern matcher for abusive terms, incitement, threats & targets
        ├── audit_log.py                       ← Tamper-evident SHA-256 hash-chain audit log manager
        ├── youtube_ingest.py                  ← YouTube Data API v3 ingestor, deep scanner & report builder
        ├── train_model.py                     ← Machine learning training utility (TF-IDF + Logistic Regression)
        ├── lexora_test_dataset.json           ← Curated benchmark dataset of Indian socio-political comments
        ├── package.json                       ← Node.js dependencies (Express, Helmet, Cors, Morgan, Concurrently)
        ├── requirements.txt                   ← Python dependencies (Flask, PyTorch, Transformers, Google-GenAI)
        ├── .env.example                       ← Environment variable template (API keys & configuration)
        │
        ├── src/                               ← Node.js Backend Application Modules
        │   ├── analyze.js                     ← Analysis service bridge (calls Flask with local JS fallback)
        │   ├── reportParser.js                ← Parser converting legacy report text into structured JSON
        │   ├── data/
        │   │   └── lexicon.js                 ← Offline fallback JS lexicon dictionary
        │   ├── middleware/
        │   │   └── requireApiKey.js           ← Express middleware enforcing LEXORA_API_KEY security
        │   └── routes/
        │       ├── analyze.js                 ← Route handler for POST /api/analyze (Single text check)
        │       ├── audit.js                   ← Route handler for GET /api/audit/log and /api/audit/verify
        │       ├── contact.js                 ← Route handler for POST /api/contact (Rate-limited submissions)
        │       └── report.js                  ← Route handler for GET/POST /api/report (Full report generation)
        │
        ├── public/                            ← Client-Side Web Application (Zero-build static UI)
        │   ├── index.html                     ← Primary landing page, live comment tester & audit viewer
        │   ├── script.js                      ← UI controller for live demo, audit logging, and stats
        │   ├── style.css                      ← Premium dark-mode styling for main dashboard
        │   ├── analysis.html                  ← Full deep-scan report viewer & interactive chart analytics
        │   ├── analysis.js                    ← Analytics controller for report generation & rendering
        │   ├── analysis.css                   ← Stylesheet for analytics & visualization panels
        │   ├── audit-trail.html               ← Dedicated standalone cryptographic evidence inspector
        │   ├── about.html                     ← Mission overview, system methodology & team credentials
        │   ├── about.js & about.css           ← Scripts and styling for team showcase
        │   └── *.jpeg                         ← Team member profile assets
        │
        ├── audit-log/                         ← Storage directory for cryptographic audit chain
        │   └── tier_audit_chain.jsonl         ← Append-only JSON Lines SHA-256 hash-chained log
        │
        ├── model-output/                      ← Local report cache storage
        │   └── youtube_feed_report.txt.json   ← Cached structured output of the latest generated scan
        │
        └── tests/                             ← Test Suites
            └── test_tier_rules.py             ← Pytest regression test suite for tier normalization rules
```

---

## 🔒 Cryptographic Audit Trail System

To ensure that flagged content (Tier 3 Hate Speech/Incitement and Tier 4 Direct Threats) can be held as tamper-evident evidence—even if original comments are later deleted or modified on social media platforms—Lexora implements an append-only cryptographic hash chain.

### How it Works:
1. **Canonical Formatting:** Every high-risk record is canonicalized using deterministic JSON key ordering (`_canonical()`).
2. **SHA-256 Linking:** The hash of entry $n$ is calculated over:
   $$\text{Hash}_n = \text{SHA256}(\text{CanonicalRecord}_n + \text{Hash}_{n-1})$$
   *(The first record links to `GENESIS_HASH` = 64 zeros).*
3. **Immutability:** Modifying, deleting, or reordering any past entry alters its hash and invalidates the entire downstream chain.
4. **Instant Verification:** `GET /api/audit/verify` recalculates the entire chain from block 0 to block $n$, immediately confirming chain integrity or pinpointing the corrupted index.

---

## 🔌 API Reference

### Express Gateway Routes (Port 3000)

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | No | Express gateway health check and timestamp. |
| `POST` | `/api/analyze` | No (Rate Limited) | Single comment classification (used by live demo widget). |
| `GET` | `/api/report` | `LEXORA_API_KEY`* | Fetches cached report or triggers fresh deep topic scan. |
| `POST` | `/api/report` | `LEXORA_API_KEY`* | Triggers live YouTube ingest and classification pipeline. |
| `GET` | `/api/audit/log` | `LEXORA_API_KEY`* | Retrieves paginated hash-chain audit log (`?limit=20&offset=0`). |
| `GET` | `/api/audit/verify` | `LEXORA_API_KEY`* | Recomputes SHA-256 chain and reports integrity status. |
| `POST` | `/api/contact` | No (Rate Limited) | Submit feedback or inquiry (rate limited to 5 per 15 min). |

*\*Note: Localhost development requests are automatically exempt from API key requirements.*

### Flask ML Service Routes (Port 5000)

| Method | Endpoint | Auth Header | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | None | Returns service status, degraded mode flag, and cache counts. |
| `POST` | `/api/classify-text` | None | Classifies a single comment string `{ "text": "..." }`. |
| `POST` | `/api/analyze` | None | Analyzes given query with comment quota. |
| `POST` | `/api/generate_report` | `X-Internal-Key` | Runs full multi-video ingestion, LLM classification & report generation. |
| `GET` | `/api/audit/log` | `X-Internal-Key` | Reads most-recent-first entries from `tier_audit_chain.jsonl`. |
| `GET` | `/api/audit/verify` | `X-Internal-Key` | Validates hash chain from genesis block to head. |

---

## 🚀 Installation & Getting Started

### Prerequisites
- **Node.js:** v18.0.0 or higher
- **Python:** v3.9 or higher
- **API Keys:**
  - YouTube Data API v3 key ([Google Cloud Console](https://console.cloud.google.com/))
  - Google Gemini API key ([Google AI Studio](https://aistudio.google.com/))

### 1. Clone the Repository
```bash
git clone https://github.com/biswasJoyeesmita/L3exora_hack.git
cd L3exora_hack
```

### 2. Set Up Python Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Install Python requirements
pip install -r requirements.txt
```

### 3. Install Node.js Dependencies
```bash
npm install
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory (copy from `.env.example`):
```bash
cp .env.example .env
```
Edit `.env` and fill in your API credentials (see [Environment Configuration](#-environment-configuration)).

### 5. Start the Application
You can run both the Express gateway and Flask ML service concurrently:

```bash
# Start both servers together
npm start

# Or start in development watch mode
npm run dev
```

Alternatively, run the services in separate terminals:
```bash
# Terminal 1 (Python ML Service)
python api_server.py

# Terminal 2 (Node Express Server)
node server.js
```

Open your browser and navigate to **`http://localhost:3000`**.

---

## ⚙️ Environment Configuration

Create `.env` in the root of `L3exora_hack/`:

```env
# Server Configuration
PORT=3000
NODE_ENV=development
CORS_ORIGIN=*

# External AI & API Credentials
GEMINI_API_KEY=your_gemini_api_key_here
YOUTUBE_API_KEY=your_youtube_data_api_key_here

# Internal Application Security
LEXORA_API_KEY=your_secure_shared_secret_key_here
START_LEXORA_PYTHON=true
PYTHON_START_TIMEOUT_MS=30000
```

> [!CAUTION]
> Never commit `.env` or expose real API keys in source control. The `.gitignore` file is configured to exclude all secret and local environment files.

---

## 🧪 Testing & Quality Assurance

### Run Regression Tests
Verify tier normalization rules and safeguard against over-flagging:
```bash
pytest tests/test_tier_rules.py -v
```

### Run Audit Chain Integrity Self-Test
Verify the cryptographic hash chain independently:
```bash
python audit_log.py
```

---

## 🏆 Target & Project Status

- **Status:** Complete production-ready architecture with live YouTube ingestion, dual-model LLM/RoBERTa routing, and cryptographic audit logging.
- **Target Initiative:** Smart India Hackathon (SIH) 2026 — AI-Driven Social Media Intelligence & Government Abuse Detection.

---

## 📄 License

This project is licensed under the [ISC License](LICENSE).