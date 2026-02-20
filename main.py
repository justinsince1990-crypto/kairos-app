"""
Kairos — NiceGUI interface.
Real-time chat via WebSockets. No page reruns. No Streamlit.
"""

import asyncio
import json
import os

from nicegui import app, ui

from heartbeat import start_heartbeat
from kairos_utils import (
    classify_memory_weight,
    load_chat_history,
    load_constitution,
    save_chat_history,
    save_constitution,
    save_memory_to_vault,
    get_response,
)

# ─────────────────────────────────────────────
# GLOBAL STATE  (single-user app)
# ─────────────────────────────────────────────
messages: list[dict] = []
ACCENT = "#ff007f"

VOICE_MAP = {
    "Aria (Confident)": "en-US-AriaNeural",
    "Jenny (Soft)":     "en-US-JennyNeural",
    "Guy (Deep)":       "en-US-GuyNeural",
}


def mood_color(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["angry", "furious", "hate", "mad"]):         return "#ff2a2a"
    if any(w in t for w in ["sad", "lonely", "miss", "depressed"]):      return "#2a7fff"
    if any(w in t for w in ["chill", "relax", "vibing", "calm"]):        return "#9d00ff"
    if any(w in t for w in ["curious", "interesting", "wonder"]):        return "#00f2ff"
    return "#ff007f"


# ─────────────────────────────────────────────
# AUDIO
# ─────────────────────────────────────────────
async def speak(text: str, audio_el: ui.audio, voice: str = "en-US-AriaNeural"):
    try:
        import edge_tts
        fname = "vault/tts_output.mp3"
        os.makedirs("vault", exist_ok=True)
        communicate = edge_tts.Communicate(text, voice, rate="+8%", pitch="-3Hz")
        await communicate.save(fname)
        audio_el.set_source(f"/vault/tts_output.mp3?t={asyncio.get_event_loop().time():.0f}")
        audio_el.play()
    except Exception:
        pass


# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
CSS = f"""
* {{ box-sizing: border-box; }}

body {{
    background: #050505;
    color: #E0E0E0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    margin: 0;
}}

/* ── scrollbar ── */
::-webkit-scrollbar {{ width: 4px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: #333; border-radius: 4px; }}

/* ── header ── */
.k-header {{
    background: rgba(8,8,8,0.97);
    border-bottom: 1px solid rgba(255,255,255,0.07);
    padding: 14px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 200;
    backdrop-filter: blur(20px);
}}

/* ── pulse dot ── */
@keyframes pulse {{
    0%, 100% {{ box-shadow: 0 0 0 0 {ACCENT}99; }}
    70%       {{ box-shadow: 0 0 0 10px transparent; }}
}}
.k-pulse {{
    width: 9px; height: 9px;
    background: {ACCENT};
    border-radius: 50%;
    animation: pulse 2.2s infinite;
    display: inline-block;
    margin-left: 10px;
}}

/* ── tabs ── */
.q-tabs {{ background: rgba(10,10,10,0.95) !important; border-bottom: 1px solid rgba(255,255,255,0.07); }}
.q-tab__label {{ font-size: 0.78rem !important; letter-spacing: 1px; }}
.q-tab--active .q-tab__label, .q-tab--active .q-icon {{ color: {ACCENT} !important; }}
.q-tab-panels {{ background: transparent !important; }}
.q-tab-panel {{ padding: 0 !important; }}

/* ── chat bubbles ── */
.k-chat {{ max-width: 820px; margin: 0 auto; padding: 20px 16px 120px; }}

.k-user {{
    background: rgba(30,30,30,0.75);
    border-radius: 18px 18px 4px 18px;
    padding: 10px 15px;
    max-width: 72%;
    margin-left: auto;
    margin-bottom: 10px;
    font-size: 0.95rem;
    line-height: 1.55;
    word-break: break-word;
}}

.k-bot {{
    border-left: 3px solid {ACCENT};
    padding: 10px 15px;
    margin-bottom: 10px;
    max-width: 88%;
    font-size: 0.95rem;
    line-height: 1.6;
    word-break: break-word;
}}

.k-bot-label {{
    font-size: 0.7rem;
    color: #555;
    letter-spacing: 1px;
    margin-bottom: 4px;
}}

/* ── input bar ── */
.k-inputbar {{
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: linear-gradient(to top, #050505 70%, transparent);
    padding: 14px 16px 20px;
    z-index: 150;
}}

.k-input .q-field__control {{
    background: rgba(18,18,18,0.95) !important;
    border-radius: 26px !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    color: #E0E0E0 !important;
    padding: 0 16px !important;
}}

.k-input .q-field__native {{ color: #E0E0E0 !important; }}

/* ── send button ── */
.k-send {{
    background: {ACCENT} !important;
    border-radius: 50% !important;
    min-width: 44px !important;
    width: 44px !important;
    height: 44px !important;
    color: white !important;
}}

/* ── vault cards ── */
.k-memory {{
    background: rgba(18,18,18,0.9);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 10px;
    font-size: 0.85rem;
    color: #bbb;
    white-space: pre-wrap;
    word-break: break-word;
}}

/* ── section titles ── */
.k-section {{ font-size: 1.3rem; font-weight: 600; color: #E0E0E0; padding: 20px 16px 10px; letter-spacing: 1px; }}
.k-sublabel {{ font-size: 0.75rem; color: #555; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 6px; }}

/* ── textarea override ── */
.k-textarea .q-field__control {{
    background: rgba(15,15,15,0.95) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    color: #ddd !important;
}}
.k-textarea .q-field__native {{ color: #ddd !important; min-height: 360px; }}
"""


# ─────────────────────────────────────────────
# PAGE
# ─────────────────────────────────────────────
@ui.page("/")
async def main():
    global messages, ACCENT
    messages = load_chat_history()
    settings = {"voice": "en-US-AriaNeural", "temperature": 1.0, "auto_play": False}

    ui.add_head_html("""
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
        <meta name="theme-color" content="#050505">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    """)
    ui.add_css(CSS)

    # ── HEADER ──
    with ui.element("div").classes("k-header w-full"):
        with ui.row().classes("items-center gap-2"):
            ui.label("KAIROS").style(f"color:{ACCENT}; font-size:1.35rem; font-weight:600; letter-spacing:4px;")
            ui.element("span").classes("k-pulse")
        ui.label("ONLINE").style("color:#444; font-size:0.7rem; letter-spacing:2px;")

    # ── TABS ──
    with ui.tabs().classes("w-full") as tabs:
        t_chat     = ui.tab("Chat",     icon="chat")
        t_voice    = ui.tab("Voice",    icon="mic")
        t_vault    = ui.tab("Vault",    icon="storage")
        t_identity = ui.tab("Identity", icon="fingerprint")
        t_senses   = ui.tab("Senses",   icon="tune")

    with ui.tab_panels(tabs, value=t_chat).classes("w-full"):

        # ════════════════════════════════
        # CHAT
        # ════════════════════════════════
        with ui.tab_panel(t_chat):
            chat_col = ui.column().classes("k-chat w-full")
            audio_el = ui.audio("").props("style='display:none'")

            # Render history
            with chat_col:
                for msg in messages:
                    if msg["role"] == "user":
                        with ui.row().classes("w-full justify-end"):
                            ui.markdown(msg["content"]).classes("k-user")
                    elif msg["role"] == "assistant":
                        with ui.column().classes("k-bot"):
                            ui.label("🧬 Kairos").classes("k-bot-label")
                            ui.markdown(msg["content"])

            # Input bar
            with ui.element("div").classes("k-inputbar"):
                with ui.row().classes("w-full items-center gap-2"):
                    msg_input = (
                        ui.input(placeholder="Message Kairos...")
                        .classes("k-input flex-grow")
                        .props("outlined dense")
                    )
                    send_btn = ui.button(icon="send").classes("k-send")

            async def send():
                global ACCENT
                text = msg_input.value.strip()
                if not text:
                    return
                msg_input.set_value("")
                messages.append({"role": "user", "content": text})

                # User bubble
                with chat_col:
                    with ui.row().classes("w-full justify-end"):
                        ui.markdown(text).classes("k-user")

                # Bot bubble (streaming)
                with chat_col:
                    bot_col = ui.column().classes("k-bot")
                    with bot_col:
                        ui.label("🧬 Kairos").classes("k-bot-label")
                        spinner = ui.spinner("dots").style(f"color:{ACCENT}")

                ui.run_javascript("window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'})")

                # Run blocking HTTP call in thread pool
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: get_response(messages, temperature=settings["temperature"]),
                )

                full_res = ""
                bot_col.clear()
                with bot_col:
                    ui.label("🧬 Kairos").classes("k-bot-label")
                    live_md = ui.markdown("▌")

                if isinstance(response, str):
                    full_res = response
                else:
                    for line in response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line.decode("utf-8")[6:])
                                chunk = data["choices"][0]["delta"].get("content", "")
                                full_res += chunk
                                live_md.set_content(full_res + "▌")
                                await asyncio.sleep(0)
                            except Exception:
                                pass

                live_md.set_content(full_res)
                ui.run_javascript("window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'})")

                # Update accent color
                ACCENT = mood_color(full_res)

                messages.append({"role": "assistant", "content": full_res})
                save_chat_history(messages)

                # Memory
                w = classify_memory_weight(text, full_res)
                if w == "heavy":
                    save_memory_to_vault(messages)
                    ui.notify("Memory Added", type="positive", icon="memory", position="top-right")

                # Audio
                if settings["auto_play"]:
                    await speak(full_res, audio_el, settings["voice"])

            msg_input.on("keydown.enter", send)
            send_btn.on("click", send)

        # ════════════════════════════════
        # VOICE
        # ════════════════════════════════
        with ui.tab_panel(t_voice):
            with ui.column().classes("w-full items-center").style("padding: 60px 20px;"):
                voice_audio_el = ui.audio("").props("style='display:none'")

                ui.element("div").style(f"""
                    width:100px; height:100px; border-radius:50%;
                    background:{ACCENT};
                    box-shadow: 0 0 40px {ACCENT}66;
                    margin-bottom: 30px;
                """)
                ui.label("TAP TO SPEAK").style("color:#555; letter-spacing:3px; font-size:0.8rem;")

                transcript_box = ui.markdown("").style("margin-top:20px; color:#aaa; text-align:center;")
                response_box   = ui.markdown("").style(
                    f"border-left:3px solid {ACCENT}; padding:16px; margin-top:20px; max-width:600px; line-height:1.6;"
                )

                ui.button("🎙️ Speak", on_click=lambda: ui.run_javascript("""
                    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
                    recognition.lang = 'en-US';
                    recognition.onresult = (e) => {
                        const transcript = e.results[0][0].transcript;
                        emitEvent('voice_input', {text: transcript});
                    };
                    recognition.start();
                """)).style(f"background:{ACCENT}; color:white; border-radius:30px; padding:12px 32px; font-size:1rem;")

                async def handle_voice(e):
                    text = e.args.get("text", "").strip()
                    if not text:
                        return
                    transcript_box.set_content(f"**You:** {text}")
                    messages.append({"role": "user", "content": text})

                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: get_response(messages, temperature=settings["temperature"]),
                    )
                    full_res = ""
                    if isinstance(response, str):
                        full_res = response
                    else:
                        for line in response.iter_lines():
                            if line:
                                try:
                                    data = json.loads(line.decode("utf-8")[6:])
                                    full_res += data["choices"][0]["delta"].get("content", "")
                                except Exception:
                                    pass

                    response_box.set_content(full_res)
                    messages.append({"role": "assistant", "content": full_res})
                    save_chat_history(messages)
                    await speak(full_res, voice_audio_el, settings["voice"])

                ui.on("voice_input", handle_voice)

        # ════════════════════════════════
        # VAULT
        # ════════════════════════════════
        with ui.tab_panel(t_vault):
            ui.label("Memory Vault").classes("k-section")
            search = ui.input(placeholder="Search memories...").classes("w-full").style("padding: 0 16px;").props("outlined dense")
            vault_col = ui.column().classes("w-full").style("padding: 0 16px;")

            def render_vault():
                vault_col.clear()
                try:
                    with open("vault/memories.txt", "r", encoding="utf-8") as f:
                        entries = [e.strip() for e in f.read().split("\n\n") if e.strip()]
                    q = search.value.lower()
                    shown = [e for e in entries if q in e.lower()] if q else entries[-15:]
                    with vault_col:
                        for entry in reversed(shown):
                            with ui.element("div").classes("k-memory"):
                                ui.label(entry)
                except FileNotFoundError:
                    with vault_col:
                        ui.label("No memories yet.").style("color:#555; padding:20px;")

            render_vault()
            search.on("input", render_vault)

        # ════════════════════════════════
        # IDENTITY
        # ════════════════════════════════
        with ui.tab_panel(t_identity):
            ui.label("Identity Matrix").classes("k-section")
            with ui.column().classes("w-full").style("padding: 0 16px 100px;"):
                identity_area = (
                    ui.textarea(value=load_constitution())
                    .classes("k-textarea w-full")
                    .props("outlined autogrow")
                )

                def save_identity():
                    save_constitution(identity_area.value, "Manual Update")
                    ui.notify("Evolved", type="positive", icon="auto_awesome", position="top-right")

                ui.button("Update Entity", on_click=save_identity).style(
                    f"background:{ACCENT}; color:white; border-radius:10px; margin-top:16px;"
                )

        # ════════════════════════════════
        # SENSES
        # ════════════════════════════════
        with ui.tab_panel(t_senses):
            ui.label("Senses & Cognition").classes("k-section")
            with ui.column().classes("w-full").style("padding: 0 16px;gap:24px;"):

                with ui.column().classes("gap-2"):
                    ui.label("AUDIO").classes("k-sublabel")
                    auto_play_sw = ui.switch("Auto-play responses", value=False)
                    auto_play_sw.on("update:model-value", lambda e: settings.update({"auto_play": e.args}))

                    voice_sel = ui.select(
                        options=list(VOICE_MAP.keys()),
                        value="Aria (Confident)",
                        label="Voice Model",
                    ).props("outlined dense dark").style("min-width:200px;")
                    voice_sel.on(
                        "update:model-value",
                        lambda e: settings.update({"voice": VOICE_MAP.get(e.args, "en-US-AriaNeural")}),
                    )

                with ui.column().classes("gap-2"):
                    ui.label("CREATIVITY").classes("k-sublabel")
                    temp_label = ui.label(f"Temperature: {settings['temperature']:.1f}").style("color:#888; font-size:0.85rem;")
                    temp_sl = ui.slider(min=0.1, max=1.5, step=0.1, value=1.0).style("max-width:300px;")

                    def on_temp(e):
                        settings["temperature"] = round(e.args, 1)
                        temp_label.set_text(f"Temperature: {settings['temperature']:.1f}")

                    temp_sl.on("update:model-value", on_temp)

                with ui.column().classes("gap-2"):
                    ui.label("VISION").classes("k-sublabel")
                    upload = ui.upload(
                        label="Show her something",
                        on_upload=lambda e: app.storage.user.update({"last_image_name": e.name}),
                    ).props("outlined accept='image/*'").style("max-width:300px;")


# ─────────────────────────────────────────────
# STATIC FILES (audio)
# ─────────────────────────────────────────────
app.add_static_files("/vault", "vault")


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────
app.on_startup(start_heartbeat)


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        title="Kairos",
        dark=True,
        favicon="🧬",
        reload=False,
        show=False,
    )
