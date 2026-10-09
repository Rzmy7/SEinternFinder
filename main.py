import os
import sys
import json
import time
import datetime
import urllib.request
import urllib.error

MAX_MESSAGE_LENGTH = 4000

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

def execute_gemini_request(model: str, payload: dict, api_key: str):
    """Executes a request to Gemini with 120s timeout and retry on 503 service unavailable."""
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
                wait_time = (attempt + 1) * 4
                print(f"Notice: Gemini service temporarily busy (503). Retrying in {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)
                continue
            raise RuntimeError(f"Gemini API error {e.code}: {err_body}")

def generate_internship_report(gemini_api_key: str) -> str:
    """Generates the daily internship digest using Gemini 3.8 Flash."""
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
    
    print("Sending prompt to Gemini 3.8 Flash...")
    result = execute_gemini_request("gemini-3.8-flash", payload, gemini_api_key)
    
    candidate = result.get("candidates", [{}])[0]
    parts = candidate.get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts)
    
    # Strip any enclosing code fences if present
    if text.startswith("```html"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def main():
    token = get_env_var("TELEGRAM_BOT_TOKEN")
    chat_id = get_env_var("TELEGRAM_CHAT_ID")
    gemini_api_key = get_env_var("GEMINI_API_KEY")
    
    if not token or not chat_id:
        print("Error: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.", file=sys.stderr)
        sys.exit(1)
        
    if not gemini_api_key:
        print("Error: Missing GEMINI_API_KEY. Get a free API key at https://aistudio.google.com/", file=sys.stderr)
        sys.exit(1)
        
    print("Generating daily internship listings via Gemini 3.8 Flash...")
    report_text = generate_internship_report(gemini_api_key)
    
    print(f"Generated report ({len(report_text)} chars). Sending to Telegram...")
    chunks = chunk_text(report_text)
    
    for i, chunk in enumerate(chunks, 1):
        res = send_telegram_message(token, chat_id, chunk, parse_mode="HTML")
        print(f"Chunk {i}/{len(chunks)} sent successfully: {res.get('ok')}")

if __name__ == "__main__":
    main()
