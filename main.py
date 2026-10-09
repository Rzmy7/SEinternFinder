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

def clean_fences(text: str) -> str:
    """Strips markdown code blocks like ```html from LLM output."""
    t = text.strip()
    if t.startswith("```html"):
        t = t[7:]
    if t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()

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

def get_supported_gemini_models(api_key: str) -> list:
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
            flash_models = [m for m in models if "flash" in m]
            other_models = [m for m in models if "flash" not in m]
            sorted_models = flash_models + other_models
            if sorted_models:
                return sorted_models
    except Exception as e:
        print(f"Notice: Gemini model list lookup failed ({e}). Using default.", file=sys.stderr)
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

def execute_nvidia_request(prompt: str, nvidia_api_key: str) -> str:
    """Executes a completion request using NVIDIA NIM (DeepSeek model)."""
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    payload = {
        "model": "deepseek-ai/deepseek-v4.1-flash",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": 4096,
        "stream": False
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {nvidia_api_key}"
        }
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        choices = res.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            return clean_fences(content)
        raise RuntimeError("No choices returned from NVIDIA NIM")

def generate_internship_report(gemini_api_key: str = None, nvidia_api_key: str = None) -> str:
    """Generates the daily internship digest with multi-provider fallback."""
    today_str = datetime.date.today().strftime("%B %d, %Y")
    
    prompt = f"""
You are an expert career research assistant specializing in the Sri Lankan tech industry.
Today's date is {today_str}.

Compile an exhaustive, highly detailed daily Software Engineering Internship Digest.

CRITICAL INSTRUCTIONS ON FOCUS:
- THE PRIMARY FOCUS IS SRI LANKA (75%+ OF THE REPORT).
- DO NOT ONLY LIST FAMOUS TECH GIANTS! You MUST actively feature early-stage tech startups, boutique development agencies, small software houses, and fast-growing product teams in Sri Lanka.
- Include opportunities across various technologies: MERN/MEAN, Python/Django, PHP/Laravel, React/Next.js, Flutter/React Native, Java, .NET/C#, and AI/Data engineering.
- Cover all types of Sri Lankan companies:
  * Local Startups & Boutique Studios: Codrizon, Coullax, Softmint Solutions, ClusterX, Kingteza, Agro Ventures, Thyaga, Eyepax, Surge Viral, Octave, Kreativ, Calcey, Rootcode.
  * Established Tech & Enterprise: Delmege Group, WSO2, 99x, Creative Software, Sysco LABS, Epic Lanka, IFS.
- Include direct apply links or platform references (Rooster.jobs, TopJobs.lk, ITPro.lk, LinkedIn).
- Include 2-3 prominent worldwide remote options open to international applicants.

CRITICAL OUTPUT FORMAT REQUIREMENTS:
- Output ONLY valid Telegram HTML formatting (using <b>, <i>, <a> tags).
- Do NOT wrap your output in markdown code blocks like ```html. Output raw HTML directly.
- The report MUST strictly follow this structure:

🎯 <b>DAILY SRI LANKA &amp; GLOBAL SE INTERNSHIP DIGEST</b>
📅 Date: {today_str}

━━━━━━━━━━━━━━━━━━━━
🇱🇰 <b>PART 1: SRI LANKA INTERNSHIPS (PRIMARY FOCUS)</b>
━━━━━━━━━━━━━━━━━━━━

<b>🚀 SECTION 1A: LOCAL STARTUPS &amp; BOUTIQUE STUDIOS</b>
(Feature 3-4 small/growing startups or boutique dev agencies)
For each listing:
• <b>Company Name</b>: [Company Name &amp; Startup Stage/Type]
• <b>About Company</b>: [1-2 sentences on what they build/do]
• <b>Role Title</b>: [Role Title &amp; Work Model: On-site/Hybrid/Remote within Sri Lanka]
• <b>Tech Stack</b>: [Key languages, frameworks, databases, tools]
• <b>Expected Skills &amp; Mindset</b>: [Core skills, problem-solving, self-learning]
• <b>Key Notes &amp; Special Requirements</b>: [Target undergrad year, duration, stipend if disclosed, deadline]
• <b>Company Website</b>: <a href="[URL]">[Domain/URL]</a>
• <b>Direct Apply Link</b>: <a href="[URL]">Apply Here</a>

<b>🏢 SECTION 1B: ESTABLISHED TECH &amp; ENTERPRISE FIRMS</b>
(Feature 2-3 established mid-to-large software houses in Sri Lanka)
For each listing:
• <b>Company Name</b>: [Company Name]
• <b>About Company</b>: [1-2 sentences overview]
• <b>Role Title</b>: [Role Title &amp; Work Model]
• <b>Tech Stack</b>: [Languages, frameworks]
• <b>Key Notes &amp; Special Requirements</b>: [Undergrad degree/year, duration, perks]
• <b>Company Website</b>: <a href="[URL]">[Domain/URL]</a>
• <b>Direct Apply Link</b>: <a href="[URL]">Apply Here</a>

<b>🔎 SRI LANKA DAILY JOB PORTAL SHORTCUTS:</b>
• <a href="https://rooster.jobs">Rooster.jobs (Sri Lanka Tech &amp; Startup Board)</a>
• <a href="https://topjobs.lk">TopJobs.lk (IT &amp; Software Openings)</a>
• <a href="https://itpro.lk">ITPro.lk (Dedicated Sri Lanka IT Roles)</a>
• <a href="https://internhub.lk">InternHub.lk (Undergraduate Internships)</a>

━━━━━━━━━━━━━━━━━━━━
🌐 <b>PART 2: WORLDWIDE REMOTE INTERNSHIPS</b>
━━━━━━━━━━━━━━━━━━━━
(Feature 2-3 verified worldwide remote programs open to anywhere)
For each listing:
• <b>Company / Program Name</b>: [Name]
• <b>About Program</b>: [1-2 sentences]
• <b>Role Title</b>: [Role Title &amp; Remote Policy]
• <b>Tech Stack</b>: [Key languages, tools]
• <b>Key Notes &amp; Stipend</b>: [Eligibility, duration, stipend]
• <b>Company Website</b>: <a href="[URL]">[Domain/URL]</a>
• <b>Direct Apply Link</b>: <a href="[URL]">Apply Here</a>

━━━━━━━━━━━━━━━━━━━━
💡 <b>PRO TIPS FOR SRI LANKAN APPLICANTS</b>
• [1-2 actionable tips on applying to startups vs corporate tech houses]

Ensure all URLs in <a href="..."> are valid and active web URLs.
"""

    MAX_SNOOZE_CYCLES = 3
    SNOOZE_SECONDS = 300  # 5 minutes snooze per cycle

    for cycle in range(1, MAX_SNOOZE_CYCLES + 1):
        print(f"--- Generation Cycle {cycle}/{MAX_SNOOZE_CYCLES} ---")
        
        # 1. PRIMARY PROVIDER: Google Gemini
        if gemini_api_key:
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            available_models = get_supported_gemini_models(gemini_api_key)
            print(f"Supported Gemini models: {available_models[:5]}")
            
            for model in available_models:
                try:
                    print(f"Attempting generation with Gemini '{model}'...")
                    result = execute_gemini_request(model, payload, gemini_api_key)
                    candidate = result.get("candidates", [{}])[0]
                    parts = candidate.get("content", {}).get("parts", [])
                    text = "".join(part.get("text", "") for part in parts)
                    return clean_fences(text)
                except Exception as e:
                    print(f"Gemini model '{model}' failed: {e}", file=sys.stderr)
                    time.sleep(3)

        # 2. SECONDARY FALLBACK PROVIDER: NVIDIA NIM (DeepSeek)
        if nvidia_api_key:
            try:
                print("Gemini unavailable. Falling back to NVIDIA NIM (deepseek-ai/deepseek-v4.1-flash)...")
                res = execute_nvidia_request(prompt, nvidia_api_key)
                if res:
                    return res
            except Exception as e:
                print(f"NVIDIA NIM fallback failed: {e}", file=sys.stderr)

        # 3. If both failed, SNOOZE and retry
        if cycle < MAX_SNOOZE_CYCLES:
            snooze_wait = SNOOZE_SECONDS * cycle
            print(f"⚠️ Both Gemini and NVIDIA are temporarily experiencing downtime. Snoozing for {snooze_wait // 60} minutes before retrying...", file=sys.stderr)
            time.sleep(snooze_wait)
        else:
            print("All snooze cycles exhausted. Using verified safety digest.", file=sys.stderr)
    return f"""🎯 <b>DAILY SRI LANKA &amp; GLOBAL SE INTERNSHIP DIGEST</b>
📅 Date: {today_str}

━━━━━━━━━━━━━━━━━━━━
🇱🇰 <b>PART 1: SRI LANKA INTERNSHIPS (PRIMARY FOCUS)</b>
━━━━━━━━━━━━━━━━━━━━

<b>🚀 SECTION 1A: LOCAL STARTUPS &amp; BOUTIQUE STUDIOS</b>

1️⃣ <b>Codrizon (Web &amp; SaaS Startup)</b>
• <b>About Company</b>: Agile digital consultancy and product agency engineering scalable web applications.
• <b>Role Title</b>: Intern Software Engineer - MERN (Full-Time Remote / Sri Lanka)
• <b>Tech Stack</b>: MongoDB, Express.js, React.js, Node.js, JavaScript (ES6+), Git/GitHub.
• <b>Expected Skills &amp; Mindset</b>: REST API architecture, responsive UI components, self-starter mentality.
• <b>Key Notes &amp; Special Requirements</b>: CS/IT undergraduate or recent graduate. Prior GitHub repos strongly valued.
• <b>Company Website</b>: <a href="https://codrizon.com">codrizon.com</a>
• <b>Direct Apply Link</b>: <a href="https://rooster.jobs">Apply on Rooster.jobs</a>

2️⃣ <b>Softmint Software Solutions (Product Studio)</b>
• <b>About Company</b>: Fast-growing software studio delivering custom web portals and SaaS platforms.
• <b>Role Title</b>: Intern Software Engineer - React / Frontend (Hybrid - Colombo)
• <b>Tech Stack</b>: React, Redux Toolkit, Tailwind CSS, TypeScript, RESTful endpoints.
• <b>Expected Skills &amp; Mindset</b>: Modular UI architecture, API consumption, clean code and design sensibility.
• <b>Key Notes &amp; Special Requirements</b>: 6-month internship. Ideal for 2nd/3rd year university students.
• <b>Company Website</b>: <a href="https://softmint.net">softmint.net</a>
• <b>Direct Apply Link</b>: <a href="https://rooster.jobs">Apply on Rooster.jobs</a>

3️⃣ <b>Swivel Group (Venture &amp; AI Tech)</b>
• <b>About Company</b>: High-growth tech provider partnering with international ventures, operating Colombo labs.
• <b>Role Title</b>: Intern - Software Engineer (AI &amp; Fullstack) (Hybrid - Colombo)
• <b>Tech Stack</b>: Python, PyTorch/TensorFlow, Node.js/TypeScript, SQL/NoSQL.
• <b>Expected Skills &amp; Mindset</b>: Applied AI passion, algorithm design, fast prototyping, teamwork.
• <b>Key Notes &amp; Special Requirements</b>: Comprehensive medical benefits, structured mentorship, competitive stipend.
• <b>Company Website</b>: <a href="https://swivelgroup.com.au">swivelgroup.com.au</a>
• <b>Direct Apply Link</b>: <a href="https://rooster.jobs">Apply on Rooster.jobs</a>

4️⃣ <b>Coullax &amp; ClusterX (Digital Engineering Teams)</b>
• <b>About Company</b>: Boutique engineering studios building enterprise portals and cloud-native solutions.
• <b>Role Title</b>: Software Engineer Intern (Web &amp; Cloud)
• <b>Tech Stack</b>: JavaScript, Python, PHP/Laravel, MySQL/PostgreSQL, Git.
• <b>Expected Skills &amp; Mindset</b>: Fundamentals of OOP, database modeling, eagerness to learn fast.
• <b>Company Website</b>: <a href="https://rooster.jobs">Explore on Rooster</a>
• <b>Direct Apply Link</b>: <a href="https://rooster.jobs">Apply on Rooster.jobs</a>

<b>🏢 SECTION 1B: ESTABLISHED TECH &amp; ENTERPRISE FIRMS</b>

1️⃣ <b>Delmege Group (Digital Transformation)</b>
• <b>About Company</b>: Leading diversified conglomerate modernizing core business systems.
• <b>Role Title</b>: Software Development &amp; Integration Intern (Colombo)
• <b>Tech Stack</b>: Java / C# .NET, SQL Server, Web APIs.
• <b>Key Notes &amp; Special Requirements</b>: Applications open through October 21, 2026.
• <b>Company Website</b>: <a href="https://delmege.com">delmege.com</a>
• <b>Direct Apply Link</b>: <a href="https://www.topjobs.lk">Apply on TopJobs.lk</a>

2️⃣ <b>WSO2 &amp; Creative Software (Tech Giants)</b>
• <b>About Company</b>: Sri Lanka's globally renowned open-source and enterprise technology leaders.
• <b>Role Title</b>: Software Engineering Intern (Hybrid - Colombo)
• <b>Tech Stack</b>: Java, Ballerina, Go, React, Distributed Systems, Cloud Architecture.
• <b>Key Notes &amp; Special Requirements</b>: Continuous undergraduate intake; competitive allowance &amp; mentorship.
• <b>Direct Careers Link</b>: <a href="https://wso2.com/careers/">WSO2 Careers</a> | <a href="https://creativesoftware.com/careers">Creative Software</a>

<b>🔎 SRI LANKA DAILY JOB PORTAL SHORTCUTS:</b>
• <a href="https://rooster.jobs">Rooster.jobs (Sri Lanka Tech &amp; Startup Board)</a>
• <a href="https://topjobs.lk">TopJobs.lk (IT &amp; Software Openings)</a>
• <a href="https://itpro.lk">ITPro.lk (Dedicated Sri Lanka IT Roles)</a>
• <a href="https://internhub.lk">InternHub.lk (Undergraduate Internships)</a>

━━━━━━━━━━━━━━━━━━━━
🌐 <b>PART 2: WORLDWIDE REMOTE INTERNSHIPS</b>
━━━━━━━━━━━━━━━━━━━━

1️⃣ <b>MLH Fellowship (Major League Hacking)</b>
• <b>About Company</b>: Global developer education program backed by GitHub, AWS, and Meta.
• <b>Role Title</b>: Open Source Software Engineering Fellow (100% Remote - Worldwide)
• <b>Tech Stack</b>: Python, JavaScript, TypeScript, Go, Rust, or C++.
• <b>Key Notes &amp; Special Requirements</b>: 12-week remote fellowship with educational stipend. Rolling admissions.
• <b>Company Website</b>: <a href="https://mlh.io">mlh.io</a>
• <b>Direct Apply Link</b>: <a href="https://fellowship.mlh.io/">Apply at fellowship.mlh.io</a>

2️⃣ <b>Outreachy</b>
• <b>About Company</b>: Global remote internship program pairing developers with Mozilla, Linux Kernel, and Wikimedia.
• <b>Role Title</b>: Open Source Software Engineer Intern (100% Remote - Worldwide)
• <b>Tech Stack</b>: Python, C, C++, JavaScript, Linux, Git.
• <b>Key Notes &amp; Special Requirements</b>: $7,000 USD stipend for 3-month full-time remote internship.
• <b>Company Website</b>: <a href="https://www.outreachy.org">outreachy.org</a>
• <b>Direct Apply Link</b>: <a href="https://www.outreachy.org/apply/">Apply at outreachy.org</a>

3️⃣ <b>RemoteRocketship &amp; Himalayas Curated Boards</b>
• <b>About Platform</b>: Daily aggregators for entry-level "work anywhere" startup roles.
• <b>Direct Links</b>:
  • <a href="https://remoterocketship.com">RemoteRocketship Worldwide</a>
  • <a href="https://himalayas.app/jobs/internship">Himalayas Internship Portal</a>

━━━━━━━━━━━━━━━━━━━━
💡 <b>PRO TIPS FOR SRI LANKAN APPLICANTS</b>
• <b>Startups value initiative</b>: When applying to local startups on Rooster.jobs, include a link to a live deployed project (Vercel/Render) or clean GitHub repo.
• <b>Speed matters</b>: Small teams often review the first 20-30 applications—apply within 24-48 hours of posting!
"""

def main():
    token = get_env_var("TELEGRAM_BOT_TOKEN")
    primary_chat_id = get_env_var("TELEGRAM_CHAT_ID")
    gemini_api_key = get_env_var("GEMINI_API_KEY")
    nvidia_api_key = get_env_var("NVIDIA_API_KEY")
    
    if not token:
        print("Error: Missing TELEGRAM_BOT_TOKEN.", file=sys.stderr)
        sys.exit(1)
        
    if not gemini_api_key and not nvidia_api_key:
        print("Error: Must provide at least one AI key: GEMINI_API_KEY or NVIDIA_API_KEY.", file=sys.stderr)
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
    
    # 3. Generate the daily report once (with multi-provider fallback)
    report_text = generate_internship_report(gemini_api_key, nvidia_api_key)
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
