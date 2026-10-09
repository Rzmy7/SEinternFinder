import os
import sys
import json
import time
import datetime
import urllib.request
import urllib.error

MAX_MESSAGE_LENGTH = 4000
SUBSCRIBERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscribers.json")

def get_env_var(name: str):
    """Fetch environment variable with Windows user registry fallback."""
    val = os.environ.get(name)
    if val:
        return val.strip()
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                val, _ = winreg.QueryValueEx(key, name)
                if val:
                    return str(val).strip()
        except Exception:
            pass
    return None

def load_subscribers() -> list:
    """Loads subscribers list from subscribers.json."""
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [int(x) for x in data if str(x).lstrip("-").isdigit()]
        except Exception as e:
            print(f"Warning: Failed to read {SUBSCRIBERS_FILE}: {e}", file=sys.stderr)
    return []

def save_subscribers(subs: list):
    """Saves unique subscribers list to subscribers.json."""
    unique_subs = sorted(list(set(subs)))
    try:
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(unique_subs, f, indent=2)
        print(f"Saved {len(unique_subs)} subscriber(s) to subscribers.json.")
    except Exception as e:
        print(f"Error saving {SUBSCRIBERS_FILE}: {e}", file=sys.stderr)

def sync_telegram_subscribers(token: str, current_subs: list) -> list:
    """Queries Telegram getUpdates to detect new /start and /stop commands."""
    subscribers = set(current_subs)
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            updates = data.get("result", [])
    except Exception as e:
        print(f"Notice: Could not fetch getUpdates ({e}). Using existing subscribers list.", file=sys.stderr)
        return list(subscribers)
        
    for update in updates:
        msg = update.get("message") or update.get("channel_post")
        if not msg:
            continue
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        text = (msg.get("text") or "").strip().lower()
        
        if not chat_id:
            continue
            
        if text.startswith("/start") or text == "hi" or text == "hello":
            if chat_id not in subscribers:
                subscribers.add(chat_id)
                welcome = (
                    "👋 <b>Welcome!</b>\n\n"
                    "You are now subscribed to the <b>Daily Software Engineering Internship Digest</b>!\n\n"
                    "🎯 Every morning at <b>8:00 AM (Asia/Colombo)</b>, you will receive active Software Engineering internship opportunities "
                    "in Sri Lanka and worldwide remote listings.\n\n"
                    "<i>(Send /stop at any time to unsubscribe)</i>"
                )
                try:
                    send_telegram_message(token, str(chat_id), welcome, parse_mode="HTML")
                    print(f"New subscriber added & greeted: {chat_id}")
                except Exception as err:
                    print(f"Failed to send welcome message to {chat_id}: {err}", file=sys.stderr)
        elif text.startswith("/stop"):
            if chat_id in subscribers:
                subscribers.remove(chat_id)
                farewell = "👋 You have successfully unsubscribed from daily internship alerts. Send /start anytime to re-subscribe!"
                try:
                    send_telegram_message(token, str(chat_id), farewell, parse_mode="HTML")
                    print(f"Subscriber removed: {chat_id}")
                except Exception:
                    pass
                    
    return list(subscribers)

def chunk_text(text: str, max_length: int = MAX_MESSAGE_LENGTH):
    """Splits text into chunks preserving line breaks."""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_len = 0
    
    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_length:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_len = 0
            while len(line) > max_length:
                chunks.append(line[:max_length])
                line = line[max_length:]
            current_chunk.append(line)
            current_len = len(line) + 1
        else:
            current_chunk.append(line)
            current_len += line_len
            
    if current_chunk:
        chunks.append("\n".join(current_chunk))
        
    return chunks

def send_telegram_message(token: str, chat_id: str, text: str, parse_mode: str = "HTML"):
    """Sends a single message to Telegram Bot API with fallback to plain text."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        if e.code == 400 and parse_mode:
            print(f"Warning: HTML parse failed, falling back to plain text. Details: {error_body}", file=sys.stderr)
            payload.pop("parse_mode", None)
            data = json.dumps(payload).encode("utf-8")
            retry_req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(retry_req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        raise RuntimeError(f"Telegram API error {e.code}: {error_body}")

def get_supported_models(api_key: str) -> list:
    """Queries ModelService to get currently available models supporting generateContent."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = []
            for m in data.get("models", []):
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    models.append(name)
            # Prioritize flash models, then pro models
            flash_models = [m for m in models if "flash" in m]
            other_models = [m for m in models if "flash" not in m]
            sorted_models = flash_models + other_models
            if sorted_models:
                return sorted_models
    except Exception as e:
        print(f"Notice: Model list lookup failed ({e}). Using default list.", file=sys.stderr)
    return ["gemini-3.8-flash"]

def execute_gemini_request(model: str, payload: dict, api_key: str):
    """Executes a request to Gemini with retry on 503 service unavailable."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            if e.code == 503 and attempt < 3:
                wait_time = (attempt + 1) * 5
                print(f"Notice: Model {model} busy (503). Retrying in {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)
                continue
            raise RuntimeError(f"Gemini API error {e.code}: {err_body}")

def generate_internship_report(gemini_api_key: str) -> str:
    """Generates the daily internship digest trying available models dynamically."""
    today_str = datetime.date.today().strftime("%B %d, %Y")
    
    prompt = f"""
You are an expert career research assistant for software engineering students and graduates.
Today's date is {today_str}.

Compile a rich, comprehensive daily Software Engineering Internship Digest.
Include real opportunities, top tech hiring companies, and programs:

1. SRI LANKA TECH COMPANIES & OPENINGS:
Highlight 4-5 companies actively hiring software engineering interns in Sri Lanka (e.g. Codrizon, Swivel Group, Delmege, Softmint Solutions, WSO2, Creative Software, Rootcode, Sysco LABS, 99x).

2. WORLDWIDE REMOTE INTERNSHIPS & FELLOWSHIPS:
Highlight 3-4 prestigious global remote programs and platforms (e.g. MLH Fellowship, Outreachy, GitLab, RemoteRocketship, Himalayas).

CRITICAL OUTPUT FORMAT REQUIREMENTS:
- Output ONLY valid Telegram HTML formatting (using <b>, <i>, <a> tags).
- Do NOT wrap your output in markdown code blocks like ```html. Output raw HTML directly.
- The report MUST strictly follow this exact 2-part structure:

🎯 <b>DAILY SOFTWARE ENGINEERING INTERNSHIP DIGEST</b>
📅 Date: {today_str}

━━━━━━━━━━━━━━━━━━━━
🇱🇰 <b>PART 1: SRI LANKA INTERNSHIPS (LOCAL)</b>
━━━━━━━━━━━━━━━━━━━━

For each listing:
• <b>Company Name</b>: [Company Name]
• <b>About Company</b>: [1-2 sentences on what the company does]
• <b>Role Title</b>: [Role Title & Work Model: On-site/Hybrid/Remote]
• <b>Tech Stack</b>: [Key languages, frameworks, databases, tools]
• <b>Expected Skills</b>: [CS fundamentals, OOP, API design, etc.]
• <b>Key Notes & Special Requirements</b>: [Target undergrad year/degree, duration, stipend, deadline/posted date]
• <b>Company Website</b>: <a href="[URL]">[Domain/URL]</a>
• <b>Direct Apply Link</b>: <a href="[URL]">Apply Here</a>

━━━━━━━━━━━━━━━━━━━━
🌐 <b>PART 2: WORLDWIDE REMOTE INTERNSHIPS</b>
━━━━━━━━━━━━━━━━━━━━

For each listing:
• <b>Company Name</b>: [Company Name]
• <b>About Company</b>: [1-2 sentences on what the company does]
• <b>Role Title</b>: [Role Title & Remote Policy]
• <b>Tech Stack</b>: [Key languages, frameworks, tools]
• <b>Expected Skills</b>: [Key competencies sought]
• <b>Key Notes & Special Requirements</b>: [Eligibility, timezone expectations, application deadline]
• <b>Company Website</b>: <a href="[URL]">[Domain/URL]</a>
• <b>Direct Apply Link</b>: <a href="[URL]">Apply Here</a>

━━━━━━━━━━━━━━━━━━━━
💡 <b>PRO TIPS FOR TODAY</b>
• [1-2 actionable tips on resumes, GitHub portfolios, or interview preparation]

Ensure all URLs in <a href="..."> are valid and active web URLs.
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    available_models = get_supported_models(gemini_api_key)
    print(f"Supported models on key: {available_models[:5]}")
    
    last_err = None
    for model in available_models:
        try:
            print(f"Attempting generation with model '{model}'...")
            result = execute_gemini_request(model, payload, gemini_api_key)
            candidate = result.get("candidates", [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts)
            if text.startswith("```html"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return text.strip()
        except Exception as e:
            print(f"Model '{model}' attempt failed: {e}", file=sys.stderr)
            last_err = e
            time.sleep(3)
            
    # Fallback template if all remote API models are busy
    print(f"All dynamic models busy ({last_err}). Using verified fallback digest.", file=sys.stderr)
    return f"""🎯 <b>DAILY SOFTWARE ENGINEERING INTERNSHIP DIGEST</b>
📅 Date: {today_str}

━━━━━━━━━━━━━━━━━━━━
🇱🇰 <b>PART 1: SRI LANKA INTERNSHIPS (LOCAL)</b>
━━━━━━━━━━━━━━━━━━━━

1️⃣ <b>Codrizon</b>
• <b>About Company</b>: Innovative software consultancy building scalable web platforms and enterprise digital products.
• <b>Role Title</b>: Intern Software Engineer - MERN (Full-Time Remote / Sri Lanka)
• <b>Tech Stack</b>: MongoDB, Express.js, React, Node.js, JavaScript (ES6+), Git/GitHub.
• <b>Expected Skills</b>: CS fundamentals & OOP, REST API design, state management, fullstack debugging.
• <b>Key Notes & Special Requirements</b>: Currently pursuing or recent graduate in CS/SE/IT. Prior projects valued.
• <b>Company Website</b>: <a href="https://codrizon.com">codrizon.com</a>
• <b>Direct Apply Link</b>: <a href="https://rooster.jobs">Apply on Rooster.jobs</a>

2️⃣ <b>Swivel Group</b>
• <b>About Company</b>: Australian technology provider with Colombo engineering centre creating enterprise AI ventures.
• <b>Role Title</b>: Intern - Software Engineer (AI & Fullstack) (Hybrid - Colombo)
• <b>Tech Stack</b>: Python, PyTorch/TensorFlow, REST APIs, JavaScript/TypeScript, SQL/NoSQL.
• <b>Expected Skills</b>: Passion for Applied AI & ML, clean code practices, testing, agile teamwork.
• <b>Key Notes & Special Requirements</b>: Full medical cover, structured mentorship, competitive internship allowance.
• <b>Company Website</b>: <a href="https://swivelgroup.com.au">swivelgroup.com.au</a>
• <b>Direct Apply Link</b>: <a href="https://rooster.jobs">Apply on Rooster.jobs</a>

3️⃣ <b>Delmege Group</b>
• <b>About Company</b>: Leading diversified conglomerate modernizing internal digital infrastructure.
• <b>Role Title</b>: Software Development & Integration Intern (Colombo)
• <b>Tech Stack</b>: Java / C# .NET, SQL Server, Web APIs.
• <b>Key Notes & Special Requirements</b>: Applications open through October 21.
• <b>Company Website</b>: <a href="https://delmege.com">delmege.com</a>
• <b>Direct Apply Link</b>: <a href="https://www.topjobs.lk">Apply on TopJobs.lk</a>

━━━━━━━━━━━━━━━━━━━━
🌐 <b>PART 2: WORLDWIDE REMOTE INTERNSHIPS</b>
━━━━━━━━━━━━━━━━━━━━

1️⃣ <b>MLH Fellowship (Major League Hacking)</b>
• <b>About Company</b>: Global developer education program backed by GitHub, AWS, and Meta.
• <b>Role Title</b>: Open Source Software Engineering Fellow (100% Remote - Worldwide)
• <b>Tech Stack</b>: Python, JavaScript, TypeScript, Go, Rust, or C++.
• <b>Key Notes & Special Requirements</b>: 12-week remote fellowship with educational stipend. Rolling admissions.
• <b>Company Website</b>: <a href="https://mlh.io">mlh.io</a>
• <b>Direct Apply Link</b>: <a href="https://fellowship.mlh.io/">Apply at fellowship.mlh.io</a>

2️⃣ <b>Outreachy</b>
• <b>About Company</b>: Global remote internship program pairing developers with Mozilla, Linux Kernel, and Wikimedia.
• <b>Role Title</b>: Open Source Software Engineer Intern (100% Remote - Worldwide)
• <b>Tech Stack</b>: Python, C, C++, JavaScript, Linux, Git.
• <b>Key Notes & Special Requirements</b>: $7,000 USD stipend for 3-month full-time remote internship.
• <b>Company Website</b>: <a href="https://www.outreachy.org">outreachy.org</a>
• <b>Direct Apply Link</b>: <a href="https://www.outreachy.org/apply/">Apply at outreachy.org</a>

3️⃣ <b>RemoteRocketship & Himalayas Curated Boards</b>
• <b>About Platform</b>: Daily aggregators for entry-level "work anywhere" startup roles.
• <b>Direct Links</b>:
  • <a href="https://remoterocketship.com">RemoteRocketship Worldwide</a>
  • <a href="https://himalayas.app/jobs/internship">Himalayas Internship Portal</a>

━━━━━━━━━━━━━━━━━━━━
💡 <b>PRO TIPS FOR TODAY</b>
• Polish your GitHub repo pinned projects with clear README setup instructions and demo videos.
• Apply within 48 hours of posting for maximum recruiter response rate.
"""

def main():
    token = get_env_var("TELEGRAM_BOT_TOKEN")
    primary_chat_id = get_env_var("TELEGRAM_CHAT_ID")
    gemini_api_key = get_env_var("GEMINI_API_KEY")
    
    if not token:
        print("Error: Missing TELEGRAM_BOT_TOKEN.", file=sys.stderr)
        sys.exit(1)
        
    if not gemini_api_key:
        print("Error: Missing GEMINI_API_KEY. Get a free API key at https://aistudio.google.com/", file=sys.stderr)
        sys.exit(1)
        
    # 1. Load existing subscribers and ensure primary chat ID is included
    subscribers = load_subscribers()
    if primary_chat_id and str(primary_chat_id).lstrip("-").isdigit():
        primary_id = int(primary_chat_id)
        if primary_id not in subscribers:
            subscribers.append(primary_id)
            
    # 2. Check getUpdates for new subscribers (/start) or unsubscribes (/stop)
    print("Checking for new bot subscribers via getUpdates...")
    updated_subscribers = sync_telegram_subscribers(token, subscribers)
    save_subscribers(updated_subscribers)
    
    if not updated_subscribers:
        print("No subscribers found to send report to. Exiting.")
        sys.exit(0)
        
    print(f"Active subscribers to receive report: {len(updated_subscribers)} {updated_subscribers}")
    
    # 3. Generate the daily report once
    report_text = generate_internship_report(gemini_api_key)
    chunks = chunk_text(report_text)
    
    # 4. Broadcast to each subscriber
    for sub_id in updated_subscribers:
        print(f"Sending digest to subscriber {sub_id}...")
        for i, chunk in enumerate(chunks, 1):
            try:
                res = send_telegram_message(token, str(sub_id), chunk, parse_mode="HTML")
                print(f"  Chunk {i}/{len(chunks)} sent to {sub_id}: {res.get('ok')}")
            except Exception as e:
                print(f"  Failed sending to {sub_id}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
