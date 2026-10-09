# Daily Software Engineering Internship Digest (Telegram Bot)

Automated daily Software Engineering internship search targeting **Sri Lanka (Local)** and **Worldwide (Remote)** opportunities, sent directly to Telegram at 8:00 AM (Asia/Colombo).

## Features
- Runs 100% in the cloud via free **GitHub Actions** (your laptop can be shut down).
- Live web search powered by Google Gemini 2.5 Flash with Google Search grounding.
- Two clearly separated sections:
  1. 🇱🇰 **Sri Lanka Internships (Local)**
  2. 🌐 **Worldwide Remote Internships**
- Includes company summary, tech stack, required skills, key eligibility notes, company website, and direct apply link.
- Automatically handles message length and delivers cleanly to Telegram.

---

## 3-Minute Setup on GitHub

### 1. Get a Free Gemini API Key
1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Click **Get API key** and create a free key.

### 2. Create a Private GitHub Repository
1. Go to [github.com/new](https://github.com/new).
2. Name your repo `se-internship-bot` and set it to **Private**.
3. Push or upload the files from this folder (`main.py`, `.gitignore`, and `.github/workflows/daily_report.yml`).

### 3. Add GitHub Secrets
In your GitHub repository:
1. Go to **Settings** > **Secrets and variables** > **Actions**.
2. Click **New repository secret** and add these 3:

| Secret Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `8605831110:AAGcvmHnnT-e3X-tJ_fzypHX_p5t30Q34Iw` |
| `TELEGRAM_CHAT_ID` | `1093696001` |
| `GEMINI_API_KEY` | *(Your free key from Google AI Studio)* |

### 4. Test It Instantly
1. Click the **Actions** tab in your GitHub repository.
2. Click **Daily SE Internship Digest** on the left.
3. Click **Run workflow** > **Run workflow**.
4. Within 30 seconds, your Telegram bot will deliver the latest digest!
