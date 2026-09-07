# LEXORA Detect Engine 🛡️

**LEXORA** is a multi-stage Content Moderation & Risk Assessment Pipeline designed to detect harmful, abusive, or threatening content in social media feeds and online discussions. It combines fast pattern matching with machine learning to filter and categorize text into actionable severity tiers for automated or human-in-the-loop review.

---

## 📌 Features

- **2-Stage Hybrid Architecture:**
  - **Stage 1 (Fast Regex / Lexicon Filter):** High-speed pattern matching using explicit regex rules to catch immediate threats and flaggable keywords (`lexicon.py`).
  - **Stage 2 (Intent & Context Classifier):** ML-driven classification utilizing TF-IDF vectorization and Logistic Regression (`tier_model.pkl`) to capture deep context, nuance, and user intent.
- **Multi-Tier Classification System:** Categorizes content into 4 precise severity tiers:
  - **Tier 1:** Lawful / Neutral Criticism *(Passed / Allowed)*
  - **Tier 2:** Abusive / Disrespectful *(Queued for Moderation)*
  - **Tier 3:** Hate Speech / Incitement *(Queued for Moderation)*
  - **Tier 4:** Direct Threat / Anti-National *(Flagged & Queued for Priority Action)*
- **Binary Output & Flagging:** Outputs a binary classification (`0` = Neutral/Lawful, `1` = Abusive/Harmful/Threatening) along with granular severity scores.
- **Human-in-the-Loop Integration:** Routes borderline and high-risk content into review queues for manual verification and aggregated policy reporting.

---

## 🏗️ Architecture Overview
┌─────────────────────────────────────────────────────────┐
                           │                 LEXORA DETECT ENGINE                    │
                           ├─────────────────────────────────────────────────────────┤
                           │                                                         │
                           │  ┌───────────────────┐    ┌──────────────────────────┐  │
                           │  │   lexicon.py      │    │  tier_model.pkl          │  │
                           │  │   (Fast Regex)    │    │  (TF-IDF + Logistic Reg) │  │
                           │  └─────────┬─────────┘    └─────────────┬────────────┘  │
                           │            │                            │               │
┌─────────────────────────┐    │            ▼                            ▼               │    ┌─────────────────────────┐
│ Simulated Social Feed   ├───►│    [ Stage 1 Filter ] ──────► [ Stage 2 Classifier ] ├───►│  Classification Output  │
│ (posts_mock / comments) │    │  (Explicit Threat/Regex)    (Intent & Full Context) │    │  (Tiers 1-4 & Flags)    │
└─────────────────────────┘    │                                                         │    └────────────┬────────────┘
└─────────────────────────────────────────────────────────┘                 │
▼
┌──────────────────────────────┐
│     HUMAN-IN-THE-LOOP        │
│       REVIEW QUEUE           │
├──────────────────────────────┤
│ • Tier 1: Lawful (Passed)    │
│ • Tier 2: Abusive (Queued)   │
│ • Tier 3: Incitement (Queued)│
│ • Tier 4: Threat (Queued)    │
└──────────────────────────────┘

---

## 🛠️ Tech Stack & Dependencies

- **Language:** Python 3.8+
- **Machine Learning & NLP:** 
  - `scikit-learn` (TF-IDF Vectorizer, Logistic Regression)
  - `pandas`, `numpy` (Data Processing & Structuring)
  - `re` (Regular Expression Engine)
- **Frontend / Dashboard (Optional):** HTML5, CSS3, JavaScript (for feed simulation and review queue presentation)

---

## 🚀 Getting Started

### Prerequisites

Ensure you have Python installed on your system:
```bash
python --version

InstallationClone the repository:Bashgit clone [https://github.com/biswasJoyeesmita/L3exora_hack.git](https://github.com/biswasJoyeesmita/L3exora_hack.git)
cd L3exora_hack
Create and activate a virtual environment (optional but recommended):Bashpython -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
Install dependencies:Bashpip install -r requirements.txt
(If requirements.txt is missing, install manually: pip install scikit-learn pandas numpy)💻 UsageRunning the Detection EngineRun the main pipeline on simulated social media feeds or comment streams:Bashpython main.py
Example Usage in PythonPythonfrom engine import LexoraDetectEngine

engine = LexoraDetectEngine()

text_sample = "This policy is completely wrong and poorly implemented."
result = engine.analyze(text_sample)

print(result)
# Output:
# {
#   "label": 0,
#   "tier": 1,
#   "status": "Passed",
#   "description": "Lawful Criticism"
# }
📊 Classification Tiers & Definitions
LabelTierSeverity LevelAction Taken0Tier 1Lawful Criticism / NeutralPassed (No action needed)1Tier 2Abusive / DisrespectfulQueued (Sent to review queue)1Tier 3Hate Speech / IncitementQueued (Priority moderation)1Tier 4Direct Threat / Anti-NationalQueued (Immediate flag & manual verification)

🏆 Project Status
Status: In active development (~80% completed for hackathon submission).

Target: Smart India Hackathon (SIH) 2026.

📜 License
Distributed under the MIT License. See LICENSE for more information.