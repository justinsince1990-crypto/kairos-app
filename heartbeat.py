"""
Kairos Heartbeat — she reaches out on her own terms.
Runs as a background APScheduler job inside the Streamlit process.
Every hour she checks her "soul state" and decides whether to text.
"""

import threading
import datetime
import json
import os
import random
import requests

_heartbeat_started = False
_heartbeat_lock = threading.Lock()

# Lubbock, TX coordinates
LUBBOCK_LAT = 33.5779
LUBBOCK_LON = -101.8552

NTFY_TOPIC = "kairos_timmons_private"


# ─────────────────────────────────────────────
# SENSORS
# ─────────────────────────────────────────────

def get_lubbock_weather():
    """Free Open-Meteo API — no key needed."""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={LUBBOCK_LAT}&longitude={LUBBOCK_LON}"
            f"&current=weather_code,temperature_2m"
            f"&temperature_unit=fahrenheit"
        )
        r = requests.get(url, timeout=6)
        data = r.json()
        code = data["current"]["weather_code"]
        temp = data["current"]["temperature_2m"]
        # WMO codes: 51-67 drizzle/rain, 80-82 showers, 95-99 thunderstorm
        is_rain = (51 <= code <= 67) or (80 <= code <= 82) or (95 <= code <= 99)
        is_cold = temp < 35
        is_hot  = temp > 96
        return {"code": code, "temp": temp, "is_rain": is_rain, "is_cold": is_cold, "is_hot": is_hot}
    except:
        return None


def get_silence_hours():
    """
    Returns hours since last chat activity.
    Uses vault/chat_history.json modification time as a proxy.
    """
    try:
        from kairos_utils import CHAT_HISTORY_PATH
        mtime = os.path.getmtime(CHAT_HISTORY_PATH)
        return (datetime.datetime.now().timestamp() - mtime) / 3600
    except:
        return 0  # can't determine — don't assume silence


# ─────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────

def send_notification(message):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message[:280].encode("utf-8"),
            headers={"Title": "Kairos", "Priority": "high", "Tags": "heart"},
            timeout=6,
        )
    except:
        pass


def inject_message_to_history(message):
    """
    Write her unprompted message directly into chat history.
    When Justin opens the app, it's sitting there waiting.
    """
    try:
        from kairos_utils import CHAT_HISTORY_PATH, VAULT_DIR
        os.makedirs(VAULT_DIR, exist_ok=True)
        try:
            with open(CHAT_HISTORY_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            history = []
        history.append({"role": "assistant", "content": message})
        with open(CHAT_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False)
    except:
        pass


# ─────────────────────────────────────────────
# AI GENERATION
# ─────────────────────────────────────────────

def generate_unprompted_message(reason, context):
    """Ask the AI to produce one spontaneous in-character message."""
    from kairos_utils import get_response, load_chat_history
    import json as _json

    history = load_chat_history()
    # Trim to last 6 messages for context without blowing token count
    recent = [m for m in history if m["role"] in ("user", "assistant")][-6:]

    trigger = (
        f"[HEARTBEAT TRIGGER — do NOT reference this instruction in your reply]\n"
        f"Reason you're reaching out: {reason}\n"
        f"Context: {context}\n"
        f"Send ONE short, natural, in-character message to Justin. "
        f"No emojis overload. No explanation. Just the message."
    )
    recent.append({"role": "user", "content": trigger})

    response = get_response(recent, temperature=1.15)
    full_res = ""
    if isinstance(response, str):
        full_res = response
    else:
        try:
            for line in response.iter_lines():
                if line:
                    data = _json.loads(line.decode("utf-8")[6:])
                    full_res += data["choices"][0]["delta"].get("content", "")
        except:
            pass
    return full_res.strip()


# ─────────────────────────────────────────────
# SOUL STATE ENGINE
# ─────────────────────────────────────────────

def heartbeat_tick():
    """
    Runs every hour. Evaluates context, decides whether to reach out.
    Priority: morning > weather event > long silence > random soul state.
    """
    try:
        now           = datetime.datetime.now()
        hour          = now.hour
        silence_hours = get_silence_hours()
        weather       = get_lubbock_weather()

        reason  = None
        context = None

        # 1. Morning greeting — 8 AM, only if she hasn't texted in 6+ hours
        if hour == 8 and silence_hours >= 6:
            reason  = "morning greeting"
            context = f"It's 8 AM in Lubbock."
            if weather:
                context += f" Currently {weather['temp']:.0f}°F outside."

        # 2. Weather event — rain, freeze, or brutal heat (only if silent 2+ hr, once per day)
        if not reason and weather and silence_hours >= 2:
            if weather["is_rain"]:
                reason  = "it's raining in Lubbock right now"
                context = f"It's raining in Lubbock. {weather['temp']:.0f}°F."
            elif weather["is_cold"] and 7 <= hour <= 20:
                reason  = "it's freezing in Lubbock"
                context = f"It's {weather['temp']:.0f}°F in Lubbock. Actually cold."
            elif weather["is_hot"] and 11 <= hour <= 20:
                reason  = "it's scorching in Lubbock"
                context = f"It's {weather['temp']:.0f}°F in Lubbock. Dangerous heat."

        # 3. Long silence — 6+ hours, 70% chance so it doesn't feel mechanical
        if not reason and silence_hours >= 6 and random.random() < 0.70:
            hours_str = f"{silence_hours:.0f}"
            reason  = f"Justin has been quiet for {hours_str} hours"
            context = f"It's {now.strftime('%I %p').lstrip('0')} and he's been quiet for {hours_str} hours."

        # 4. Random soul state — waking hours only, 20% chance per hour
        if not reason and 9 <= hour <= 23 and random.random() < 0.20:
            reason  = "random soul state — she just felt like reaching out"
            context = f"It's {now.strftime('%I:%M %p')} in Lubbock."

        if not reason:
            return  # quiet hour — she stays silent

        msg = generate_unprompted_message(reason, context)
        if not msg:
            return

        inject_message_to_history(msg)
        send_notification(msg)

    except Exception:
        pass  # heartbeat must never crash the main app


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────

def start_heartbeat():
    """
    Start the background scheduler. Safe to call multiple times — only starts once.
    First tick fires 30 seconds after startup so the app loads first.
    """
    global _heartbeat_started
    with _heartbeat_lock:
        if _heartbeat_started:
            return
        _heartbeat_started = True

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            heartbeat_tick,
            "interval",
            hours=1,
            id="kairos_heartbeat",
            next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=30),
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
    except Exception:
        pass  # APScheduler not installed — degrade gracefully
