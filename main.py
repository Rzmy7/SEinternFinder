import os
import sys
import json
import time
import datetime
import urllib.request
import urllib.error
import re

MAX_MESSAGE_LENGTH = 4000
SUBSCRIBERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscribers.json")

# Standard headers to prevent blocking by portals
PORTAL_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5'
}

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
                    "🎯 Every morning, you will receive active Software Engineering internship opportunities "
                    "scraped live from Sri Lankan tech companies and global teams.\n\n"
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

def scrape_live_itpro_jobs() -> list:
    """Scrapes active tech & SE internships from ITPro.lk."""
    print("Scraping live internships from ITPro.lk...")
    jobs = []
    try:
        req = urllib.request.Request("https://itpro.lk/jobs/internship/", headers=PORTAL_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            
        cards = re.findall(r'<article class="job-card"[^>]*id="([^"]+)"[^>]*>(.*?)</article>', html, re.DOTALL)
        for jid, card in cards:
            link_m = re.search(r'href="([^"]+)"', card)
            title_m = re.search(r'<h[0-9][^>]*>(.*?)</h[0-9]>', card, re.DOTALL)
            comp_m = re.search(r'<div class="jc-company"[^>]*>\s*<span[^>]*>(.*?)</span>', card, re.DOTALL) or re.search(r'class="jc-company"[^>]*>(.*?)<', card, re.DOTALL)
            loc_m = re.search(r'class="jc-location"[^>]*>(.*?)<', card, re.DOTALL)
            date_m = re.search(r'<time[^>]*>(.*?)</time>', card, re.DOTALL)
            
            if link_m and title_m:
                title = re.sub(r'<[^>]+>', ' ', title_m.group(1)).strip()
                comp = re.sub(r'<[^>]+>', ' ', comp_m.group(1)).strip() if comp_m else "Sri Lanka Tech"
                loc = re.sub(r'<[^>]+>', ' ', loc_m.group(1)).strip() if loc_m else "Sri Lanka"
                posted = re.sub(r'<[^>]+>', ' ', date_m.group(1)).strip() if date_m else ""
                
                t_low = title.lower()
                # Prioritize SE, web, AI, cloud, QA, and dev
                if any(k in t_low for k in ['developer', 'software', 'engineer', 'ai', 'data', 'web', 'full stack', 'qa', 'frontend', 'backend', 'devops', 'tech']):
                    jobs.append({
                        "portal": "ITPro.lk",
                        "company": comp,
                        "title": title,
                        "location": loc,
                        "posted": posted,
                        "url": link_m.group(1)
                    })
    except Exception as e:
        print(f"Notice: ITPro.lk scraping error ({e})", file=sys.stderr)
    print(f"Scraped {len(jobs)} relevant listings from ITPro.lk")
    return jobs

def scrape_live_topjobs() -> list:
    """Scrapes active IT & SE vacancies and internships from TopJobs.lk (Area SDQ)."""
    print("Scraping live internships & trainee roles from TopJobs.lk...")
    jobs = []
    try:
        req = urllib.request.Request("https://topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA=SDQ", headers=PORTAL_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            
        pattern = re.compile(r'<tr[^>]*onclick="createAlert\(\'([^\']+)\',\'([^\']+)\',\'([^\']+)\',\'([^\']+)\',\'([^\']+)\'\)"[^>]*>(.*?)</tr>', re.DOTALL)
        matches = pattern.findall(html)
        
        for rid, ac, jc, ec, uid, content in matches:
            title_m = re.search(r'<h2><span>(.*?)</span></h2>', content, re.DOTALL)
            comp_m = re.search(r'<h1>(.*?)</h1>', content, re.DOTALL)
            opening_m = re.search(r'<td[^>]*nowrap[^>]*>\s*([A-Za-z]{3}\s+[A-Za-z]{3}\s+\d+\s+\d{4})', content)
            
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ""
            comp = re.sub(r'<[^>]+>', '', comp_m.group(1)).strip() if comp_m else ""
            opening = opening_m.group(1).strip() if opening_m else ""
            
            url = f"https://topjobs.lk/employer/JobAdvertismentServlet?rid={rid}&ac={ac}&jc={jc}&ec={ec}"
            
            t_low = title.lower()
            if any(k in t_low for k in ['intern', 'trainee', 'associate', 'junior']):
                if any(k in t_low for k in ['software', 'developer', 'engineer', 'web', 'full stack', '.net', 'angular', 'qa', 'data', 'ai', 'system', 'cloud', 'it']):
                    jobs.append({
                        "portal": "TopJobs.lk",
                        "company": comp,
                        "title": title,
                        "location": "Sri Lanka",
                        "posted": opening,
                        "url": url
                    })
    except Exception as e:
        print(f"Notice: TopJobs.lk scraping error ({e})", file=sys.stderr)
    print(f"Scraped {len(jobs)} relevant listings from TopJobs.lk")
    return jobs

def get_scraped_jobs_payload() -> str:
    """Combines live scraped jobs into structured text for LLM contextualization."""
    itpro = scrape_live_itpro_jobs()
    topjobs = scrape_live_topjobs()
    all_jobs = itpro[:8] + topjobs[:10]
    
    if not all_jobs:
        return "No live scraped jobs found at this moment."
        
    lines = []
    for idx, j in enumerate(all_jobs, 1):
        lines.append(f"{idx}. [{j['portal']}] Company: {j['company']} | Role: {j['title']} | Location: {j['location']} | Posted/Opening: {j['posted']} | Link: {j['url']}")
    return "\n".join(lines)

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
    """Generates the daily internship digest using live scraped job data and multi-provider AI formatting."""
    today_str = datetime.date.today().strftime("%B %d, %Y")
    
    # 1. Scrape real live job listings directly from web portals
    scraped_jobs_text = get_scraped_jobs_payload()
    print("Scraped live jobs data extracted. Preparing prompt...")
    
    prompt = f"""
You are an expert career research assistant specializing in the Sri Lankan tech ecosystem.
Today's date is {today_str}.

We have just SCRAPED LIVE ACTIVE VACANCIES from Sri Lankan tech portals (ITPro.lk & TopJobs.lk).
Here are the actual live jobs currently accepting applications:
----------------------------------------
{scraped_jobs_text}
----------------------------------------

TASK:
Compile an exhaustive, highly detailed daily Software Engineering Internship Digest.
You MUST prioritize and feature the REAL SCRAPED JOBS listed above so that users get 100% active, verified openings with real links!

CRITICAL INSTRUCTIONS ON FOCUS & RATIO:
- ABSOLUTE #1 PRIORITY: SRI LANKA LOCAL INTERNSHIPS (80%+ OF THE DIGEST).
- Part 1 must feature at least 5-6 Sri Lankan listings directly derived from the REAL SCRAPED listings above (e.g. Nuwali Digital Solutions, PrimeWave Lab, Ravigno, Med Cube, Delmege, Epic Lanka, etc.).
- Categorize them clearly:
  * Section 1A: Startups & Boutique Studios
  * Section 1B: Established Tech & Enterprise Firms
- Preserve the exact application links (<a href="[URL]">Apply Here</a>) from the scraped data so applicants can immediately apply.
- Part 2 (Worldwide Remote): Include 2 curated global remote startup / fellowship opportunities (e.g. MLH Fellowship, Outreachy, or YC Work at a Startup).

CRITICAL OUTPUT FORMAT REQUIREMENTS:
- Output ONLY valid Telegram HTML formatting (using <b>, <i>, <a> tags).
- Do NOT wrap your output in markdown code blocks like ```html. Output raw HTML directly.
- The report MUST strictly follow this structure:

🎯 <b>🇱🇰 SRI LANKA SE INTERNSHIP DIGEST (DAILY LIVE VERIFIED)</b>
📅 Date: {today_str}

━━━━━━━━━━━━━━━━━━━━
🇱🇰 <b>PART 1: SRI LANKA INTERNSHIPS (CORE FOCUS - 80%)</b>
━━━━━━━━━━━━━━━━━━━━

<b>🚀 SECTION 1A: LOCAL STARTUPS &amp; BOUTIQUE STUDIOS</b>
(Feature 3-4 scraped small/growing startups or boutique dev agencies in Sri Lanka)
For each listing:
• <b>Company Name</b>: [Company Name &amp; Startup Stage/Type]
• <b>Role Title</b>: [Role Title &amp; Work Model: On-site/Hybrid/Remote within Sri Lanka]
• <b>Tech Stack</b>: [Key languages, frameworks, databases, tools relevant to the role]
• <b>Expected Skills &amp; Mindset</b>: [Core skills, problem-solving, self-learning]
• <b>Key Notes &amp; Special Requirements</b>: [Undergrad eligibility, posted date, deadline]
• <b>Direct Apply Link</b>: <a href="[REAL_SCRAPED_URL]">Apply Here</a>

<b>🏢 SECTION 1B: ESTABLISHED TECH &amp; ENTERPRISE FIRMS</b>
(Feature 2-3 scraped established mid-to-large software houses in Sri Lanka)
For each listing:
• <b>Company Name</b>: [Company Name]
• <b>Role Title</b>: [Role Title &amp; Work Model]
• <b>Tech Stack</b>: [Languages, frameworks]
• <b>Key Notes &amp; Special Requirements</b>: [Undergrad degree/year, duration, notes]
• <b>Direct Apply Link</b>: <a href="[REAL_SCRAPED_URL]">Apply Here</a>

<b>🔎 SRI LANKA DAILY JOB PORTAL SHORTCUTS:</b>
• <a href="https://itpro.lk/jobs/internship/">ITPro.lk (Dedicated Sri Lanka IT Roles)</a>
• <a href="https://topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA=SDQ">TopJobs.lk (IT &amp; Software Openings)</a>
• <a href="https://rooster.jobs">Rooster.jobs (Sri Lanka Tech &amp; Startup Board)</a>
• <a href="https://internhub.lk">InternHub.lk (Undergraduate Internships)</a>

━━━━━━━━━━━━━━━━━━━━
🌐 <b>PART 2: WORLDWIDE REMOTE INTERNSHIPS (GLOBAL STARTUPS &amp; TEAMS)</b>
━━━━━━━━━━━━━━━━━━━━

<b>🚀 SECTION 2A: GLOBAL REMOTE STARTUPS &amp; DISTRIBUTED TEAMS</b>
(Feature 2 remote-first international startups or early-stage product teams)
For each listing:
• <b>Company Name &amp; Focus</b>: [Startup Name &amp; Focus]
• <b>Role Title &amp; Remote Policy</b>: [Role Title &amp; 100% Remote Worldwide]
• <b>Tech Stack</b>: [Key languages, frameworks]
• <b>Direct Apply Link</b>: <a href="[URL]">Apply Here</a>

<b>🌍 SECTION 2B: GLOBAL DEVELOPER FELLOWSHIPS</b>
(Feature 1-2 recognized paid international programs, e.g. MLH Fellowship, Outreachy)
• <b>Program Name</b>: [Name]
• <b>Role Title</b>: [Role Title &amp; Remote details]
• <b>Stipend &amp; Duration</b>: [Stipend, duration]
• <b>Direct Apply Link</b>: <a href="[URL]">Apply Here</a>

<b>🔎 GLOBAL STARTUP JOB SEARCH SHORTCUTS:</b>
• <a href="https://wellfound.com">Wellfound (formerly AngelList - Worldwide Startups)</a>
• <a href="https://www.workatastartup.com">Y Combinator (Work at a Startup - Remote Roles)</a>
• <a href="https://remoterocketship.com">RemoteRocketship (Verified Worldwide Remote)</a>
• <a href="https://himalayas.app/jobs/internship">Himalayas (Internship Portal)</a>

━━━━━━━━━━━━━━━━━━━━
💡 <b>PRO TIPS FOR APPLICANTS (LOCAL &amp; GLOBAL)</b>
• [1-2 actionable tips on applying to startups, showcasing public GitHub work, and async communication]

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

    # Hard safety fallback if everything fails
    return f"""🎯 <b>DAILY SRI LANKA &amp; GLOBAL SE INTERNSHIP DIGEST</b>
📅 Date: {today_str}

━━━━━━━━━━━━━━━━━━━━
🇱🇰 <b>PART 1: SRI LANKA INTERNSHIPS (LIVE DIRECT PORTALS)</b>
━━━━━━━━━━━━━━━━━━━━

1️⃣ <b>PrimeWave Lab (Pvt) Ltd</b>
• <b>Role Title</b>: Full Stack Developer Intern (Remote / Sri Lanka)
• <b>Direct Apply Link</b>: <a href="https://itpro.lk/jobs/internship/">Apply on ITPro.lk</a>

2️⃣ <b>Nuwali Digital Solutions</b>
• <b>Role Title</b>: Full Stack Developer Intern (Kandy / Sri Lanka)
• <b>Direct Apply Link</b>: <a href="https://itpro.lk/jobs/internship/">Apply on ITPro.lk</a>

3️⃣ <b>Delmege Group</b>
• <b>Role Title</b>: Intern - Software Development &amp; Integration
• <b>Direct Apply Link</b>: <a href="https://topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA=SDQ">Apply on TopJobs.lk</a>

4️⃣ <b>Ravigno (Pvt) Ltd</b>
• <b>Role Title</b>: Software Engineering Intern
• <b>Direct Apply Link</b>: <a href="https://topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA=SDQ">Apply on TopJobs.lk</a>

<b>🔎 SRI LANKA DAILY JOB PORTAL SHORTCUTS:</b>
• <a href="https://itpro.lk/jobs/internship/">ITPro.lk (Dedicated Sri Lanka IT Roles)</a>
• <a href="https://topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA=SDQ">TopJobs.lk (IT &amp; Software Openings)</a>
• <a href="https://rooster.jobs">Rooster.jobs (Sri Lanka Tech &amp; Startup Board)</a>
• <a href="https://internhub.lk">InternHub.lk (Undergraduate Internships)</a>
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
    
    # 3. Generate the daily report once (with multi-source live scraper + AI formatting)
    report_text = generate_internship_report(gemini_api_key, nvidia_api_key)
    chunks = chunk_text(report_text)
    
    # 4. Broadcast to all active subscribers
    for sub_id in updated_subscribers:
        print(f"Sending live scraped digest to subscriber {sub_id}...")
        for i, chunk in enumerate(chunks, 1):
            try:
                res = send_telegram_message(token, str(sub_id), chunk, parse_mode="HTML")
                print(f"  Chunk {i}/{len(chunks)} sent to {sub_id}: {res.get('ok')}")
            except Exception as e:
                print(f"  Failed sending to {sub_id}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
