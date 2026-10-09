# 🚀 Daily Software Engineering Internship Digest (Telegram Bot)

An automated, serverless, cloud-native daily Software Engineering (SE) internship scouting system. Every day at **8:00 AM (Asia/Colombo / UTC+5:30)**, it gathers curated Software Engineering internship openings with an **80%+ focus on Sri Lankan tech startups and software studios**, secondary worldwide remote roles, and delivers formatted, actionable digests straight to Telegram subscribers.

---

## 📑 Table of Contents
1. [Key Features](#-key-features)
2. [Architecture & System Flow](#-architecture--system-flow)
3. [AI Model Fallback & Snooze Strategy](#-ai-model-fallback--snooze-strategy)
4. [Multi-User Auto-Subscription (How Users Join)](#-multi-user-auto-subscription-how-users-join)
5. [Digest Content Structure](#-digest-content-structure)
6. [Repository Structure](#-repository-structure)
7. [Environment Variables & GitHub Secrets](#-environment-variables--github-secrets)
8. [Setup & Deployment Guide](#-setup--deployment-guide)
9. [Manual Testing & Triggering](#-manual-testing--triggering)
10. [Troubleshooting & FAQs](#-troubleshooting--faqs)

---

## 🌟 Key Features

- **100% Free & Cloud-Native**: Powered by GitHub Actions cron scheduling. No server hosting, VPS, or running laptop required.
- **Heavy Sri Lanka Focus (80%+ Ratio)**: Prioritizes local software houses, early-stage boutique startups, product studios, and enterprise firms across Sri Lanka (Rooster.jobs, TopJobs.lk, ITPro.lk, InternHub.lk).
- **Secondary Global Remote Coverage**: Curates open-source fellowships (MLH, Outreachy) and remote startup engineering roles (Y Combinator, Wellfound, RemoteRocketship).
- **Multi-Provider AI Resilience**:
  - Primary: Google Gemini (`v1beta/models` dynamic resolution, e.g. `gemini-3.8-flash` / `gemini-2.5-flash`).
  - Secondary Failover: NVIDIA NIM (`deepseek-ai/deepseek-v4.1-flash`).
  - Automatic Snooze-and-Retry Loop: 3-cycle exponential backoff (5m, 10m backoff) before falling back to verified safety digest.
- **Dynamic Multi-User Subscriptions**: Anyone can subscribe to the bot by sending `/start`. Subscribers are tracked in `subscribers.json` and committed automatically back to the repository via GitHub Actions bot.
- **Resilient Telegram Delivery**: Automatic HTML sanitization, long message chunking (< 4000 characters), and automatic fallback to plain-text formatting if HTML tags are malformed.

---

## 🏗️ Architecture & System Flow

```
┌─────────────────────────────────────────────────────────────┐
│                 GitHub Actions Cloud Runner                 │
│              Cron: Every day at 08:00 AM Colombo             │
│                     (02:30 AM UTC)                          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       main.py       │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
┌───────────────────────┐             ┌───────────────────────┐
│ Sync Bot Subscribers  │             │ Generate Daily Report │
│   (Telegram API       │             │                       │
│    getUpdates)        │             │ 1. Google Gemini      │
│  - Detects /start     │             │    (Model autodiscover│
│  - Greets new users   │             │ 2. NVIDIA NIM Fallback│
│  - Detects /stop      │             │    (DeepSeek v4.1)    │
│  - Writes to          │             │ 3. 3-Cycle Snooze     │
│    subscribers.json   │             │ 4. Fallback Digest    │
└───────────┬───────────┘             └───────────┬───────────┘
            │                                     │
            └──────────────────┬──────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Broadcast to Users  │
                    │ - Message chunking  │
                    │ - HTML parse-retry  │
                    │ - Loop subscribers │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Auto-Commit Step    │
                    │ git commit & push   │
                    │ subscribers.json    │
                    └─────────────────────┘
```

---

## 🛡️ AI Model Fallback & Snooze Strategy

To ensure zero failed mornings, the generation pipeline utilizes a 4-tier resilience hierarchy:

1. **Tier 1: Google Gemini (Primary)**
   - Queries `https://generativelanguage.googleapis.com/v1beta/models` dynamically to filter all models supporting `generateContent`.
   - Prioritizes flash variants (e.g. `gemini-3.8-flash`, `gemini-2.5-flash`).
   - Retries automatically if Google returns HTTP 503 load spikes.
2. **Tier 2: NVIDIA NIM (Secondary Failover)**
   - If Gemini keys fail, exceed rate limits, or encounter downtime, requests automatically transfer to `https://integrate.api.nvidia.com/v1/chat/completions`.
   - Model: `deepseek-ai/deepseek-v4.1-flash`.
3. **Tier 3: Snooze & Retry Loop**
   - If both external AI providers are temporarily unresponsive, the script pauses (snoozes for 5–10 minutes) across 3 cycles instead of failing immediately.
4. **Tier 4: Offline Safety Digest**
   - If all cloud AI endpoints are unreachable, it dispatches an embedded, verified software engineering internship briefing containing active Sri Lankan portals and startup career links.

---

## 👥 Multi-User Auto-Subscription (How Users Join)

Users do not need to be manually added to configuration files.

1. Anyone with Telegram opens the bot: **[@SE_intern_pissu_bot](https://t.me/SE_intern_pissu_bot)**
2. The user taps **Start** or sends `/start`.
3. During the next automated run (or manual trigger), `main.py` calls Telegram's `getUpdates` API:
   - Identifies new chat IDs.
   - Sends an immediate personalized welcome greeting.
   - Appends their ID to `subscribers.json`.
4. The workflow's Git step automatically commits and pushes the updated `subscribers.json` back to your repo using `[skip ci]`.
5. If a user sends `/stop`, they are automatically removed and sent a farewell confirmation.

---

## 📋 Digest Content Structure

Each delivered Telegram digest contains:

### 🇱🇰 Part 1: Sri Lanka Internships (Core Focus - 80%+)
- **Section 1A: Local Startups & Boutique Studios**: Highlights 3–4 early-stage startups and small software agencies (e.g., Codrizon, Coullax, ClusterX, Softmint, Swivel, Calcey, Rootcode).
- **Section 1B: Established Tech & Enterprise Firms**: Mid-to-large software enterprises (e.g., Delmege, WSO2, 99x, Creative Software, Sysco LABS, IFS).
- **Per Listing Details**:
  - Company Name & Stage/Type
  - Company Overview (What they build)
  - Role Title & Work Model (On-site / Hybrid / Remote within Sri Lanka)
  - Tech Stack (Languages, Frameworks, DBs)
  - Expected Skills & Mindset
  - Key Notes (Target undergraduate year, duration, stipend, deadline)
  - Direct Website & Application Link
- **Local Portal Shortcuts**: Instant access links to Rooster.jobs, TopJobs.lk, ITPro.lk, and InternHub.lk.

### 🌐 Part 2: Worldwide Remote Internships (Secondary Addition)
- **Section 2A: Global Remote Startups**: Y Combinator backed startups, Wellfound early-stage teams, and open-source product companies.
- **Section 2B: Global Developer Fellowships**: Recognized paid programs such as MLH Fellowship, Outreachy, and Google Summer of Code.
- **International Portal Shortcuts**: Wellfound, Work at a Startup (YC), RemoteRocketship, and Himalayas.

### 💡 Part 3: Pro Tips for Applicants
- Strategic advice on technical portfolio building, cold outreach, and async work culture.

---

## 📁 Repository Structure

```
SEinternFinder/
├── .github/
│   └── workflows/
│       └── daily_report.yml     # GitHub Actions workflow (schedule + dispatch + auto-commit)
├── .gitignore                   # Ignores __pycache__, environment files, and local IDE configs
├── main.py                      # Core engine (subscriber sync, AI calling, snooze, chunking, dispatch)
├── README.md                    # Complete project documentation
└── subscribers.json             # Live database of registered Telegram subscriber chat IDs
```

---

## 🔑 Environment Variables & GitHub Secrets

The script requires the following secrets configured under **Settings > Secrets and variables > Actions**:

| Secret Name | Description | Example / Source |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot authorization token provided by [@BotFather](https://t.me/BotFather) | `8605831110:AAGcvmH...` |
| `TELEGRAM_CHAT_ID` | Primary admin Telegram chat ID (seeded automatically) | `1093696001` |
| `GEMINI_API_KEY` | Google AI Studio free API key | Obtained from [aistudio.google.com](https://aistudio.google.com/) |
| `NVIDIA_API_KEY` | NVIDIA NIM API key for DeepSeek fallback | Obtained from [build.nvidia.com](https://build.nvidia.com/) |

---

## ⚙️ Setup & Deployment Guide

### Step 1: Clone Repository
```bash
git clone https://github.com/Rzmy7/SEinternFinder.git
cd SEinternFinder
```

### Step 2: Configure GitHub Repository Permissions
To allow GitHub Actions to commit changes to `subscribers.json`:
1. Navigate to your repository on GitHub.
2. Go to **Settings** ➔ **Actions** ➔ **General**.
3. Under **Workflow permissions**, select **Read and write permissions**.
4. Check **Allow GitHub Actions to create and approve pull requests**.
5. Click **Save**.

### Step 3: Configure GitHub Secrets
1. Go to **Settings** ➔ **Secrets and variables** ➔ **Actions**.
2. Click **New repository secret** and add all 4 secrets listed in the table above.

### Step 4: Schedule Timeline
The workflow is defined in `.github/workflows/daily_report.yml`:
```yaml
on:
  schedule:
    # 8:00 AM Asia/Colombo (UTC+5:30) is 2:30 AM UTC
    - cron: '30 2 * * *'
  workflow_dispatch:
```
GitHub Actions will execute this daily without any intervention.

---

## 🧪 Manual Testing & Triggering

### Triggering via GitHub Web Interface
1. Go to the **Actions** tab in your repository.
2. In the left sidebar, click **Daily SE Internship Digest**.
3. Click the **Run workflow** dropdown button on the right.
4. Select `Branch: main` and click **Run workflow**.
5. Within ~1 minute, all subscribers will receive the latest report on Telegram.

### Running Locally (Optional)
If running on a local machine with Python 3.10+:
```bash
# On Windows PowerShell:
$env:TELEGRAM_BOT_TOKEN="your_token"
$env:TELEGRAM_CHAT_ID="your_chat_id"
$env:GEMINI_API_KEY="your_gemini_key"
$env:NVIDIA_API_KEY="your_nvidia_key"
python main.py
```

---

## ❓ Troubleshooting & FAQs

### Q: Why did a user not receive the digest after tapping `/start`?
**A**: Telegram's Bot API stores updates until read. When the scheduled workflow runs (or when you trigger it manually), it reads `getUpdates`, greets the user, records them into `subscribers.json`, and sends them the digest in that same run.

### Q: What happens if Gemini hits rate limits (429) or is busy (503)?
**A**: The system automatically switches models or transfers the query to NVIDIA NIM (DeepSeek). If both encounter downtime, the workflow snoozes for 5–10 minutes before retrying up to 3 times.

### Q: How are messages formatted for Telegram?
**A**: Telegram messages are limited to 4096 characters. The script automatically divides reports into safe chunks (< 4000 characters) preserving paragraph boundaries. If any HTML tag is unclosed, it catches the error and retries delivery in safe plain text so no message is lost.

### Q: How do I stop receiving alerts?
**A**: Simply send `/stop` to the Telegram bot. The bot will recognize the command during the next run, remove your ID from `subscribers.json`, and send a farewell confirmation.
