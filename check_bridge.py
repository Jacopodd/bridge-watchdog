import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


PING_FILE = Path("last_ping.json")
STATE_FILE = Path("state.json")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def send_telegram_message(text: str) -> None:
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_ids_raw = os.environ["TELEGRAM_CHAT_IDS"]

    chat_ids = [
        chat_id.strip()
        for chat_id in chat_ids_raw.split(",")
        if chat_id.strip()
    ]

    if not chat_ids:
        raise RuntimeError("Nessun TELEGRAM_CHAT_IDS configurato")

    for chat_id in chat_ids:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
        }).encode("utf-8")

        request = urllib.request.Request(url, data=data, method="POST")

        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()


def main() -> None:
    max_age_minutes = int(os.environ.get("PING_MAX_AGE_MINUTES", "150"))
    max_age_seconds = max_age_minutes * 60

    ping = load_json(PING_FILE)
    state = load_json(STATE_FILE)

    now_unix = int(time.time())

    service = ping.get("service", "bridge-optosensing")
    host = ping.get("host", "pc-server")
    last_ping_utc = ping.get("last_ping_utc", "unknown")
    last_ping_unix = int(ping.get("last_ping_unix", 0))

    age_seconds = now_unix - last_ping_unix
    age_minutes = round(age_seconds / 60, 1)

    previous_status = state.get("status", "unknown")

    state["last_checked_unix"] = now_unix

    if age_seconds <= max_age_seconds:
        print(f"OK - {service} attivo. Ultimo ping: {last_ping_utc}. Ritardo: {age_minutes} minuti.")

        if previous_status == "down":
            message = (
                "✅ BRIDGE RIPRISTINATO\n\n"
                f"Servizio: {service}\n"
                f"Host: {host}\n"
                f"Ultimo ping UTC: {last_ping_utc}\n"
                f"Ritardo attuale: {age_minutes} minuti\n"
                f"Soglia configurata: {max_age_minutes} minuti"
            )

            send_telegram_message(message)
            state["last_recovery_sent_unix"] = now_unix

        state["status"] = "up"
        save_json(STATE_FILE, state)
        return

    print(f"ERRORE - {service} non attivo. Ultimo ping: {last_ping_utc}. Ritardo: {age_minutes} minuti.")

    if previous_status != "down":
        message = (
            "⚠️ BRIDGE NON ATTIVO\n\n"
            f"Servizio: {service}\n"
            f"Host: {host}\n"
            f"Ultimo ping UTC: {last_ping_utc}\n"
            f"Ritardo: {age_minutes} minuti\n"
            f"Soglia configurata: {max_age_minutes} minuti\n\n"
            "Possibili cause:\n"
            "- bridge.py fermo\n"
            "- PC server spento o bloccato\n"
            "- connessione Internet assente\n"
            "- errore nell'aggiornamento del ping su GitHub"
        )

        send_telegram_message(message)
        state["last_alert_sent_unix"] = now_unix

    state["status"] = "down"
    save_json(STATE_FILE, state)


if __name__ == "__main__":
    main()