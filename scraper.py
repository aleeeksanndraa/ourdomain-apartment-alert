import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

URL = "https://southeast-thisisourdomain.securerc.co.uk/onlineleasing/ourdomain-amsterdam-south-east/floorplans.aspx"

# Exact unit names to watch for (lowercase, partial match)
TARGET_NAMES = [
    "studio suite",
    "1 bedroom",
]

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STATUS_FILE      = Path("status.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://google.com",
}


def fetch_page():
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def find_available_units(html):
    """
    Looks for unit cards that:
      1. Have a name containing 'studio suite' or '1 bedroom'
      2. Contain '(available)' OR a 'check availability' button
         — NOT just a 'get notified' button (means unavailable)
    """
    soup = BeautifulSoup(html, "html.parser")
    found = []

    # Try to find unit containers — SecureRC sites typically use divs with
    # class names like 'fpItem', 'floorplan', 'unit', or similar.
    # We search the full page text block by block.
    candidates = (
        soup.find_all(class_=lambda c: c and any(
            x in c.lower() for x in ["floorplan", "fpitem", "unit", "plan", "suite", "apartment", "listing"]
        ))
        or soup.find_all("div", recursive=True)  # fallback: all divs
    )

    # Deduplicate by text to avoid nested div double-counting
    seen = set()
    for el in candidates:
        text = el.get_text(" ", strip=True)
        text_lower = text.lower()

        # Must match one of our target unit names
        matched_name = next((n for n in TARGET_NAMES if n in text_lower), None)
        if not matched_name:
            continue

        # Skip if we've already processed a parent element with same text
        key = text[:120]
        if key in seen:
            continue
        seen.add(key)

        # Determine availability
        has_available_text   = "(available)" in text_lower
        has_check_button     = "check availability" in text_lower
        has_notified_button  = "get notified" in text_lower

        is_available = has_available_text or has_check_button
        is_unavailable = has_notified_button and not is_available

        if is_unavailable:
            continue  # unit exists but not available — skip

        if is_available:
            found.append({
                "name": text[:200],
                "matched": matched_name,
            })

    return found


def send_telegram(message):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(api_url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }, timeout=10)


def write_status(units, fetch_ok):
    existing = {}
    if STATUS_FILE.exists():
        try:
            existing = json.loads(STATUS_FILE.read_text())
        except:
            pass
    history = existing.get("history", [])
    entry = {
        "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": fetch_ok,
        "count": len(units),
        "units": [u["name"][:120] for u in units],
    }
    history.insert(0, entry)
    history = history[:200]
    STATUS_FILE.write_text(json.dumps({
        "last_checked": entry["time"],
        "total_checks": existing.get("total_checks", 0) + 1,
        "total_alerts": existing.get("total_alerts", 0) + (1 if units else 0),
        "history": history,
    }, indent=2))


def main():
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking page...")
    fetch_ok = True
    units = []

    try:
        html = fetch_page()
        units = find_available_units(html)
    except Exception as e:
        print(f"Fetch failed: {e}")
        fetch_ok = False

    write_status(units, fetch_ok)

    if units:
        print(f"FOUND {len(units)} unit(s) — sending alert!")
        lines = [
            "\U0001F3E0 <b>OurDomain unit available!</b>",
            f"{datetime.utcnow().strftime('%d %b %H:%M')} UTC",
            "",
        ]
        for u in units:
            lines.append(f"\u2705 <b>{u['matched'].title()}</b>")
            lines.append(f"<code>{u['name'][:200]}</code>")
            lines.append("")
        lines.append(f'<a href="{URL}">\u27A1\uFE0F Check availability &amp; apply now</a>')
        send_telegram("\n".join(lines))
    else:
        print("No available units found yet.")


if __name__ == "__main__":
    main()
