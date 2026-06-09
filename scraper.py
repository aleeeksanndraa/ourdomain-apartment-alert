import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

URL = "https://southeast-thisisourdomain.securerc.co.uk/onlineleasing/ourdomain-amsterdam-south-east/floorplans.aspx"
TARGET_KEYWORDS      = ["studio", "1 bed", "1bed", "1-bed", "one bed", "1 bedroom", "1bedroom"]
UNAVAILABLE_KEYWORDS = ["waitlist", "wait list", "not available", "sold out", "fully leased", "no units"]
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36","Accept-Language": "en-GB,en;q=0.9","Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Referer": "https://google.com"}

def fetch_page():
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text

def find_available_units(html):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    candidates = (soup.find_all(class_=lambda c: c and any(x in c.lower() for x in ["floorplan","fpitem","unit","plan","apartment"])) or soup.find_all("tr"))
    for el in candidates:
        text = el.get_text(" ", strip=True).lower()
        if not any(kw in text for kw in TARGET_KEYWORDS): continue
        if any(kw in text for kw in UNAVAILABLE_KEYWORDS): continue
        available_signals = ["available","apply now","apply","lease","select","rent now","book"]
        is_available = any(sig in text for sig in available_signals)
        found.append({"name": el.get_text(" ", strip=True)[:200], "available": is_available})
    return found

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}, timeout=10)

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking page...")
    try:
        html = fetch_page()
    except Exception as e:
        print(f"Fetch failed: {e}"); return
    units = find_available_units(html)
    if units:
        print(f"Found {len(units)} unit(s)!")
        lines = ["\U0001F3E0 <b>OurDomain unit available!</b>", f"Found <b>{len(units)}</b> studio/1-bed — {datetime.now().strftime('%d %b %H:%M')}", ""]
        for i, u in enumerate(units, 1):
            status = "\u2705 Likely available" if u["available"] else "\u26A0\uFE0F Check manually"
            lines += [f"{i}. {status}", f"<code>{u['name'][:150]}</code>", ""]
        lines.append(f'<a href="{URL}">\u27A1\uFE0F Apply now</a>')
        send_telegram("\n".join(lines))
    else:
        print("No matching units yet.")

if __name__ == "__main__":
    main()
