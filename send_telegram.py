import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import html

FEED_FILE = "feed.xml"
STATE_FILE = "sent_ids.json"
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def load_sent_ids():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_sent_ids(sent_ids):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(sent_ids)), f, indent=2)


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    sent_ids = load_sent_ids()
    tree = ET.parse(FEED_FILE)
    root = tree.getroot()

    # Supporta sia RSS 2.0 (<item>) che Atom (<entry>)
    items = root.findall(".//item")
    is_atom = False
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        is_atom = True

    new_items = []
    for item in items:
        if is_atom:
            ns = "{http://www.w3.org/2005/Atom}"
            guid_el = item.find(f"{ns}id")
            title_el = item.find(f"{ns}title")
            link_el = item.find(f"{ns}link")
            link = link_el.attrib.get("href", "") if link_el is not None else ""
        else:
            guid_el = item.find("guid")
            title_el = item.find("title")
            link_el = item.find("link")
            link = link_el.text.strip() if link_el is not None and link_el.text else ""

        title = title_el.text.strip() if title_el is not None and title_el.text else "Nuovo atto"
        item_id = (guid_el.text.strip() if guid_el is not None and guid_el.text else link) or title

        if item_id not in sent_ids:
            new_items.append((item_id, title, link))

    # Invia in ordine cronologico (dal più vecchio al più recente tra i nuovi)
    for item_id, title, link in reversed(new_items):
        safe_title = html.escape(title)
        safe_link = html.escape(link)
        msg = f"📄 <b>{safe_title}</b>\n\n🔗 <a href=\"{safe_link}\">Consulta l'atto</a>"
        
        send_telegram_message(msg)
        sent_ids.add(item_id)
        time.sleep(1.5)  # Rispetta i rate limit di Telegram

    save_sent_ids(sent_ids)
    print(f"Inviati {len(new_items)} nuovi atti su Telegram.")


if __name__ == "__main__":
    main()
