import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FEED_FILE = "feed.xml"
STATE_FILE = "sent_ids.json"
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
}


def load_sent_ids():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_sent_ids(sent_ids):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(sent_ids)), f, indent=2)


def clean_html_description(raw_desc):
    if not raw_desc:
        return ""
    # Sostituisce <br> e </p> con a capo prima di rimuovere i tag HTML
    text = re.sub(r"<br\s*/?>", "\n", raw_desc, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).strip()
    # Normalizza righe vuote multiple
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def format_hashtags(categories, max_tags=4):
    hashtags = []
    seen = set()
    for cat in categories:
        # Mantiene solo lettere e numeri (inclusi caratteri accentati), capitalizzando le parole
        words = re.findall(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+", cat)
        if not words:
            continue
        tag = "#" + "".join(w[0].upper() + w[1:] for w in words)
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            hashtags.append(tag)
        if len(hashtags) >= max_tags:
            break
    return " ".join(hashtags)


def build_message(item):
    title_el = item.find("title")
    link_el = item.find("link")
    desc_el = item.find("description")
    creator_el = item.find("dc:creator", NS)
    cat_els = item.findall("category")

    title = title_el.text.strip() if title_el is not None and title_el.text else "Nuovo atto"
    link = link_el.text.strip() if link_el is not None and link_el.text else ""
    creator = creator_el.text.strip() if creator_el is not None and creator_el.text else ""
    raw_desc = desc_el.text if desc_el is not None and desc_el.text else ""
    categories = [c.text.strip() for c in cat_els if c.text and c.text.strip()]

    clean_desc = clean_html_description(raw_desc)
    hashtags = format_hashtags(categories, max_tags=4)

    parts = [f"📄 <b>{html.escape(title)}</b>"]

    if creator:
        parts.append(f"🏛 <i>{html.escape(creator)}</i>")

    # Se la descrizione non inizia con 📄 (quindi è un riassunto AI vero e proprio), includila
    if clean_desc and not clean_desc.startswith("📄"):
        # Limita la descrizione per restare ampiamente sotto il limite di 4096 caratteri di Telegram
        if len(clean_desc) > 3000:
            clean_desc = clean_desc[:2997] + "..."
        parts.append(f"\n{html.escape(clean_desc)}")

    if link:
        parts.append(f"\n🔗 <a href=\"{html.escape(link)}\">Consulta l'atto sull'Albo Pretorio</a>")

    if hashtags:
        parts.append(f"\n{html.escape(hashtags)}")

    return "\n".join(parts)


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    sent_ids = load_sent_ids()
    tree = ET.parse(FEED_FILE)
    root = tree.getroot()
    items = root.findall(".//item")

    new_items = []
    for item in items:
        guid_el = item.find("guid")
        link_el = item.find("link")
        title_el = item.find("title")

        guid = guid_el.text.strip() if guid_el is not None and guid_el.text else ""
        link = link_el.text.strip() if link_el is not None and link_el.text else ""
        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        item_id = guid or link or title

        if item_id and item_id not in sent_ids:
            new_items.append((item_id, item))

    # Pubblica dal più vecchio al più recente tra i nuovi atti rilevati
    for item_id, item in reversed(new_items):
        msg = build_message(item)
        send_telegram_message(msg)
        sent_ids.add(item_id)
        time.sleep(1.5)

    save_sent_ids(sent_ids)
    print(f"Inviati {len(new_items)} nuovi atti su Telegram.")


if __name__ == "__main__":
    main()
