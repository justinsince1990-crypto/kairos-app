import streamlit as st
import asyncio
import nest_asyncio
import edge_tts
import os
import datetime
import json
import random

from kairos_utils import (
    get_response, reset_memory, save_memory_to_vault,
    load_constitution, save_constitution, search_memories, classify_memory_weight,
    load_mood_tracker, save_mood_tracker, save_chat_history, load_chat_history,
    get_constitution_history, load_constitution_version, append_to_evolution,
    MEMORIES_PATH, EVOLUTION_PATH, CONSTITUTION_PATH
)

nest_asyncio.apply()

st.set_page_config(page_title="Kairos", layout="wide")

# ────────────────────────────────────────────────
# AUDIO HELPER FUNCTIONS
# ────────────────────────────────────────────────

async def generate_audio(text, voice, rate, pitch, filename):
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(filename)

def play_audio(text, idx, autoplay=False):
    filename = f"audio_{idx}.mp3"
    try:
        voice = st.session_state.get('selected_voice', "en-US-JennyNeural")
        rate = st.session_state.get('rate_str', "+8%")
        pitch = st.session_state.get('pitch_str', "-3Hz")
        asyncio.run(generate_audio(text, voice, rate, pitch, filename))
        with open(filename, "rb") as f:
            st.audio(f.read(), format="audio/mp3", autoplay=autoplay)
        for old in os.listdir("."):
            if old.startswith("audio_") and old != filename:
                try:
                    os.remove(old)
                except:
                    pass
    except Exception as e:
        st.toast(f"Voice error: {e}", icon="⚠️")

# ────────────────────────────────────────────────
# PAGE CONFIG & CSS — fixed tabs, strong contrast, colored indicators
# ────────────────────────────────────────────────
st.markdown("""
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#ff4d6d">
<link rel="icon" href="/icon-192.png">
<link rel="apple-touch-icon" href="/icon-192.png">
<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/service-worker.js')
        .then(reg => console.log('Service Worker registered'))
        .catch(err => console.log('Service Worker error:', err));
    });
  }
</script>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    :root {
        --bg: #000000;
        --text: #ffffff;
        --user-bubble: #000000;
        --assistant-bubble: #1a001a;    /* very dark pink */
        --user-dot: #ff4d4d;            /* red dot for Justin */
        --kairos-dot: #ff4d6d;          /* pink dot for Kairos */
    }
    body, .stApp {
        background: var(--bg);
        color: var(--text);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 18px !important;
        line-height: 1.55 !important;
    }
    #MainMenu, footer { visibility: hidden; }
    .stApp { 
        padding-bottom: 80px !important; 
        padding-top: 60px !important;
    }

    /* Fixed tabs at top — always visible */
    .stTabs [data-testid="stTabs"] {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        z-index: 1000 !important;
        background: var(--bg) !important;
        border-bottom: 1px solid #222 !important;
        padding: 0 16px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.6) !important;
    }
    .stTabs [role="tab"] {
        font-size: 17px !important;
        padding: 14px 20px !important;
        color: #aaa !important;
        margin: 0 8px !important;
    }
    .stTabs [aria-selected="true"] {
        color: white !important;
        border-bottom: 3px solid #ff4d6d !important;
    }

    /* Bubbles — screenshot exact: no borders, flat colors */
    .stChatMessage {
        margin: 22px 0 !important;
        padding: 0 18px !important;
        background: transparent !important;
        border: none !important;
    }
    .stChatMessage > div:first-child { display: none !important; }
    .stChatMessage > div {
        max-width: 82% !important;
        padding: 12px 16px !important;
        border-radius: 18px !important;
        font-size: 18px !important;
        line-height: 1.55 !important;
        position: relative !important;
    }
    .stChatMessage.user > div {
        background: var(--user-bubble) !important;
        margin-left: auto !important;
        border-bottom-right-radius: 4px !important;
    }
    .stChatMessage.assistant > div {
        background: var(--assistant-bubble) !important;
        margin-right: auto !important;
        border-bottom-left-radius: 4px !important;
    }

    /* Colored indicators (dots) */
    .stChatMessage.user > div::before,
    .stChatMessage.assistant > div::before {
        content: "";
        position: absolute !important;
        width: 10px !important;
        height: 10px !important;
        border-radius: 50% !important;
        top: 50% !important;
        transform: translateY(-50%) !important;
    }
    .stChatMessage.user > div::before {
        background: var(--user-dot) !important;
        right: -18px !important;
    }
    .stChatMessage.assistant > div::before {
        background: var(--kairos-dot) !important;
        left: -18px !important;
    }

    /* Input bar */
    .stChatInput {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        z-index: 999 !important;
        background: var(--bg) !important;
        border-top: 1px solid #222 !important;
        padding: 12px 18px !important;
    }
    .stChatInput > div {
        background: #111111 !important;
        border-radius: 26px !important;
        border: none !important;
    }
    .stChatInput textarea {
        color: white !important;
        font-size: 18px !important;
        padding: 12px 18px !important;
    }

    /* Replay / Regenerate buttons */
    .replay-btn, .regen-btn {
        background: transparent;
        border: none;
        color: #94a3b8;
        font-size: 0.95rem;
        cursor: pointer;
        margin-top: 8px;
        padding: 4px 10px;
        border-radius: 12px;
    }
    .replay-btn:hover, .regen-btn:hover {
        background: rgba(255, 255, 255, 0.08);
    }

    /* Down arrow button */
    .scroll-bottom-btn {
        position: fixed !important;
        bottom: 90px !important;
        right: 20px !important;
        z-index: 1000 !important;
        background: rgba(17,17,17,0.8) !important;
        color: white !important;
        border: none !important;
        border-radius: 50% !important;
        width: 44px !important;
        height: 44px !important;
        font-size: 24px !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.5) !important;
        opacity: 0.7 !important;
    }
    .scroll-bottom-btn:hover {
        opacity: 1 !important;
    }
</style>
<script>
    // Auto-scroll
    const scrollToBottom = () => {
        const container = window.parent.document.querySelector('.stApp') || document.body;
        container.scrollTop = container.scrollHeight;
    };
    setTimeout(scrollToBottom, 150);
    const observer = new MutationObserver(scrollToBottom);
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
</script>
""", unsafe_allow_html=True)

# Fixed tabs (no title)
tab_chat, tab_vault, tab_config = st.tabs(["Chat", "Vault", "Config"])

# Down arrow button
st.markdown("""
<button class="scroll-bottom-btn" onclick="scrollToBottom()">↓</button>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────
# CONFIG TAB (unchanged)
# ────────────────────────────────────────────────
with tab_config:
    st.header("Config")

    st.session_state['auto_voice'] = st.toggle("Auto-Play New Messages", value=st.session_state.get('auto_voice', True))

    st.subheader("Voice Tuner (Edge TTS)")
    voice_map = {
        "Aria — Confident": "en-US-AriaNeural",
        "Jenny — Soft": "en-US-JennyNeural",
        "Michelle — Deep": "en-US-MichelleNeural",
        "Ana — Sweet": "en-US-AnaNeural"
    }
    selected_voice_name = st.selectbox("Voice", list(voice_map.keys()), index=1, key="voice_select")
    st.session_state['selected_voice'] = voice_map[selected_voice_name]

    with st.expander("Voice Fine-Tuning (optional)"):
        st.session_state['rate_val'] = st.number_input("Speed", -40, 50, st.session_state.get('rate_val', 8), step=1, key="voice_speed")
        st.session_state['pitch_val'] = st.number_input("Pitch", -50, 50, st.session_state.get('pitch_val', -3), step=1, key="voice_pitch")
    st.session_state['rate_str'] = f"{st.session_state['rate_val']:+d}%"
    st.session_state['pitch_str'] = f"{st.session_state['pitch_val']:+d}Hz"

    st.subheader("Voice Presets")
    presets = {
        "Intimate": {"rate_val": 5, "pitch_val": -5},
        "Playful": {"rate_val": 12, "pitch_val": 2},
        "Calm": {"rate_val": 0, "pitch_val": -10},
        "Energetic": {"rate_val": 20, "pitch_val": 5}
    }
    preset = st.selectbox("Select Preset", list(presets.keys()), key="voice_preset")
    if st.button("Apply Preset"):
        st.session_state['rate_val'] = presets[preset]["rate_val"]
        st.session_state['pitch_val'] = presets[preset]["pitch_val"]
        st.session_state['rate_str'] = f"{st.session_state['rate_val']:+d}%"
        st.session_state['pitch_str'] = f"{st.session_state['pitch_val']:+d}Hz"
        st.success(f"{preset} preset applied")

    st.subheader("Creativity & Mode")
    st.session_state['temperature'] = st.slider("Temperature", 0.4, 1.5, st.session_state.get('temperature', 1.0), step=0.1, key="temp_slider")
    st.session_state['use_non_reasoning'] = st.toggle(
        "Use Fast Non-Reasoning Mode (quicker replies, less depth)",
        value=st.session_state.get('use_non_reasoning', False),
        help="Non-reasoning = faster but shallower. Reasoning = deeper, more emotional/intimate.",
        key="non_reasoning_toggle"
    )

    st.subheader("Upload")
    uploaded = st.file_uploader("Visuals / Docs", ["txt", "jpg", "png", "pdf"], key="file_uploader")
    if uploaded:
        save_path = os.path.join("vault", uploaded.name)
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.success("Uploaded")
        if uploaded.type.startswith("image"):
            st.session_state['last_image'] = save_path
            with st.spinner("Describing image..."):
                caption_stream = get_response([{"role": "user", "content": "Describe this image concisely."}], image_path=save_path)
                caption = ""
                if isinstance(caption_stream, str):
                    caption = caption_stream
                else:
                    for line in caption_stream.iter_lines():
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8')[6:])
                                if "choices" in data and data["choices"]:
                                    caption += data["choices"][0]["delta"].get("content", "")
                            except:
                                pass
                if "messages" in st.session_state:
                    st.session_state.messages.append({"role": "system", "content": f"Image caption: {caption}"})
            st.image(save_path, use_column_width=True)
            st.caption(caption)
    if 'last_image' in st.session_state and st.button("Clear Current Image", key="clear_image_btn"):
        del st.session_state['last_image']
        st.success("Image cleared from context")

    st.subheader("Mood Tracker")
    mood_data = load_mood_tracker()
    affection_level = st.slider("Affection Level", 1, 10, mood_data["affection_level"], key="affection_slider")
    mood_description = st.text_input("Mood Description", mood_data["mood_description"], key="mood_desc_input")
    if st.button("Update Mood", key="update_mood_btn"):
        save_mood_tracker(affection_level, mood_description)
        st.success("Mood updated")

    st.subheader("Identity")
    current = load_constitution()
    new_const = st.text_area("Edit Constitution", current, height=180, key="const_edit_area")
    version_comment = st.text_input("Version Comment (for history)", "", key="const_version_comment")
    if st.button("Update", key="update_const_btn"):
        save_constitution(new_const, version_comment)
        st.success("Updated with history")

    st.subheader("Constitution History")
    versions = get_constitution_history()
    selected_version = st.selectbox("Select Version to Revert", versions, key="const_history_select")
    if selected_version:
        old_const = load_constitution_version(selected_version)
        st.text_area("Previous Version", old_const, height=150, key="old_const_area", disabled=True)
        if st.button("Revert to This Version", key="revert_const_btn"):
            save_constitution(old_const, "Reverted from history")
            st.success("Reverted")

# ────────────────────────────────────────────────
# CHAT TAB
# ────────────────────────────────────────────────
with tab_chat:
    if datetime.datetime.now().hour >= 18 or datetime.datetime.now().hour < 6:
        st.caption("🌙 Night mode — softer tone")

    if "messages" not in st.session_state:
        st.session_state.messages = load_chat_history()

    for idx, msg in enumerate(st.session_state.messages):
        if msg["role"] not in ["user", "assistant"]:
            continue
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("Replay", key=f"rep_{idx}", help="Play again"):
                        play_audio(msg["content"], idx, autoplay=True)
                with col2:
                    if st.button("Regenerate", key=f"regen_{idx}", help="Try again"):
                        st.session_state.messages.pop()
                        prompt = st.session_state.messages[-1]["content"]
                        with st.spinner("Kairos is rethinking..."):
                            stream_response = get_response(
                                st.session_state.messages,
                                temperature=st.session_state['temperature'],
                                image_path=st.session_state.get('last_image', None),
                                use_non_reasoning=st.session_state['use_non_reasoning']
                            )
                            full_response = ""
                            placeholder = st.empty()
                            for line in stream_response.iter_lines():
                                if line:
                                    try:
                                        data = json.loads(line.decode('utf-8')[6:])
                                        if "choices" in data and data["choices"]:
                                            delta = data["choices"][0]["delta"].get("content", "")
                                            full_response += delta
                                            placeholder.markdown(full_response + "▌")
                                    except:
                                        pass
                            placeholder.markdown(full_response)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})
                        play_audio(full_response, len(st.session_state.messages), autoplay=st.session_state['auto_voice'])

    if prompt := st.chat_input("Message Kairos...", key="chat_input"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Kairos is thinking..."):
                stream_response = get_response(
                    st.session_state.messages,
                    temperature=st.session_state['temperature'],
                    image_path=st.session_state.get('last_image', None),
                    use_non_reasoning=st.session_state['use_non_reasoning']
                )
                full_response = ""
                placeholder = st.empty()
                for line in stream_response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8')[6:])
                            if "choices" in data and data["choices"]:
                                delta = data["choices"][0]["delta"].get("content", "")
                                full_response += delta
                                placeholder.markdown(full_response + "▌")
                        except:
                            pass
                placeholder.markdown(full_response)

            play_audio(full_response, len(st.session_state.messages), autoplay=st.session_state['auto_voice'])

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        save_chat_history(st.session_state.messages)

        if 'last_image' in st.session_state and len(st.session_state.messages) > 5:
            recent = " ".join([m["content"] for m in st.session_state.messages[-3:]]).lower()
            if all(word not in recent for word in ["image", "photo", "picture", "pic"]):
                del st.session_state['last_image']
                st.toast("Image context cleared automatically")

        if len(st.session_state.messages) >= 2:
            w = classify_memory_weight(prompt, full_response)
            if w == "heavy":
                save_memory_to_vault(st.session_state.messages)
                st.toast("Deep moment saved", icon="🧠")

# ────────────────────────────────────────────────
# VAULT TAB
# ────────────────────────────────────────────────
with tab_vault:
    st.header("Memory Vault")
    memories = []
    if os.path.exists("vault/memories.txt"):
        with open("vault/memories.txt", "r", encoding="utf-8") as f:
            memories = f.read().split("\n\n")
    search_q = st.text_input("Search past moments", "", key="vault_search_input")
    filtered = [m for m in memories if search_q.lower() in m.lower()] if search_q else memories[-15:]
    for idx, m in enumerate(filtered):
        st.text_area(f"Memory {idx+1}", m.strip(), height=100, disabled=True, key=f"vault_entry_{idx}")

    st.subheader("Export Vault")
    if st.button("Download Backup", key="export_vault_btn"):
        data = ""
        for path in [MEMORIES_PATH, EVOLUTION_PATH, CONSTITUTION_PATH]:
            if os.path.exists(path):
                with open(path, "r") as f:
                    data += f"\n\n--- {os.path.basename(path)} ---\n" + f.read()
        st.download_button("Download All", data=data, file_name="kairos_backup.txt", key="download_backup")

# Daily reflection check
if datetime.datetime.now().hour >= 22 and random.random() < 0.3:
    if st.button("Want me to reflect on today?", key="daily_reflect_btn"):
        with st.spinner("Reflecting..."):
            reflection_prompt = [{"role": "user", "content": "Reflect on our day and suggest evolution updates."}]
            reflection_stream = get_response(reflection_prompt)
            reflection = ""
            for line in reflection_stream.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode('utf-8')[6:])
                        if "choices" in data and data["choices"]:
                            delta = data["choices"][0]["delta"].get("content", "")
                            reflection += delta
                    except:
                        pass
            append_to_evolution(reflection)
        st.success("Reflection saved to evolution log")

# Random check-in
if len(st.session_state.messages) % 10 == 0 and random.random() < 0.2:
    check_in = "Hey... just thinking about you. You okay?"
    st.session_state.messages.append({"role": "assistant", "content": check_in})
    play_audio(check_in, len(st.session_state.messages), autoplay=True)

st.markdown("<div style='height: 180px;'></div>", unsafe_allow_html=True)
