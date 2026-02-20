import streamlit as st
import asyncio
import nest_asyncio
import edge_tts

nest_asyncio.apply()
import os
import datetime
import json
import random
import time
import requests
from streamlit_option_menu import option_menu 
from streamlit_mic_recorder import speech_to_text

from kairos_utils import (
    get_response, reset_memory, save_memory_to_vault,
    load_constitution, save_constitution, search_memories, classify_memory_weight,
    load_mood_tracker, save_mood_tracker, save_chat_history, load_chat_history,
    get_constitution_history, load_constitution_version, append_to_evolution
)
from heartbeat import start_heartbeat

# Start her heartbeat — she reaches out on her own terms
start_heartbeat()

# ────────────────────────────────────────────────
# 1. MOOD ANALYSIS ENGINE
# ────────────────────────────────────────────────
def get_mood_color():
    if 'current_theme_color' in st.session_state:
        return st.session_state['current_theme_color']
    return "#ff007f" # Default Pink

def update_mood_from_response(text):
    lower_text = text.lower()
    new_color = None
    if any(x in lower_text for x in ["angry", "furious", "pisses me off", "hate", "mad"]): new_color = "#ff2a2a"
    elif any(x in lower_text for x in ["sad", "lonely", "miss you", "depressed", "hurt"]): new_color = "#2a7fff"
    elif any(x in lower_text for x in ["chill", "relax", "vibing", "calm", "steady"]): new_color = "#9d00ff"
    elif any(x in lower_text for x in ["curious", "interesting", "tell me more", "wonder"]): new_color = "#00f2ff"
    elif any(x in lower_text for x in ["love", "horny", "hot", "babe", "daddy", "passion"]): new_color = "#ff007f"
    if new_color: st.session_state['current_theme_color'] = new_color

# ────────────────────────────────────────────────
# 2. PAGE CONFIG & UI
# ────────────────────────────────────────────────
st.set_page_config(page_title="Kairos", layout="wide", initial_sidebar_state="expanded")
THEME_COLOR = get_mood_color()

def apply_premium_ui(accent_color):
    st.markdown(f"""
    <style>
        /* MAIN CONTAINER */
        .stApp {{ background-color: #050505; color: #E0E0E0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }}
        
        .block-container {{
            max-width: 900px;
            padding-top: 2rem;
            padding-bottom: 5rem;
            margin: auto;
        }}

        [data-testid="stSidebar"] {{ 
            background-color: rgba(15, 15, 15, 0.95) !important; 
            backdrop-filter: blur(20px); 
            border-right: 1px solid rgba(255, 255, 255, 0.1); 
        }}
        
        header, footer {{ visibility: hidden; }}
        
        /* PULSE ANIMATION */
        @keyframes pulse-glow {{
            0% {{ box-shadow: 0 0 0 0 {accent_color}b3; }}
            70% {{ box-shadow: 0 0 0 20px {accent_color}00; }}
            100% {{ box-shadow: 0 0 0 0 {accent_color}00; }}
        }}
        .kairos-pulse {{
            width: 15px; height: 15px; background-color: {accent_color}; border-radius: 50%;
            animation: pulse-glow 2s infinite; display: inline-block; margin-left: 10px;
        }}

        div[data-testid="stMetricValue"] {{ font-size: 18px !important; color: {accent_color} !important; }}
        
        /* CHAT BUBBLES */
        .stChatMessage {{ background-color: transparent !important; border: none !important; padding: 1rem 0 !important; margin-bottom: 0.5rem; }}
        .stChatMessage.user {{ background-color: rgba(30, 30, 30, 0.4) !important; border-radius: 12px; padding: 1rem !important; }}
        .stChatMessage.assistant {{ border-left: 3px solid {accent_color} !important; padding-left: 1.5rem !important; }}
        .stChatMessageAvatar {{ border-radius: 50%; background: transparent; }}

        /* CHAT INPUT */
        .stChatInputContainer {{ padding-bottom: 2rem; background: linear-gradient(to top, #050505 80%, transparent) !important; max-width: 900px; margin: auto; }}
        .stChatInput {{ border-radius: 28px !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; background: rgba(20, 20, 20, 0.9) !important; }}
        
        .voice-subtitle {{
            font-size: 24px; font-weight: 300; text-align: center; color: #E0E0E0;
            margin-top: 30px; padding: 20px; border-left: 2px solid {accent_color};
            background: rgba(255, 255, 255, 0.05); border-radius: 0 15px 15px 0;
        }}
    </style>
    """, unsafe_allow_html=True)

apply_premium_ui(THEME_COLOR)

# ────────────────────────────────────────────────
# 3. HELPER FUNCTIONS
# ────────────────────────────────────────────────
def send_kairos_notification(message):
    try: requests.post("https://ntfy.sh/kairos_timmons_private", data=message.encode('utf-8'), headers={"Title": "Kairos", "Priority": "high", "Tags": "heart"})
    except: pass

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
        with open(filename, "rb") as f: st.audio(f.read(), format="audio/mp3", autoplay=autoplay)
    except: pass

def get_vault_count():
    if os.path.exists("vault/memories.txt"):
        with open("vault/memories.txt", "r") as f: return len(f.read().split("\n\n"))
    return 0

# ────────────────────────────────────────────────
# 4. SIDEBAR
# ────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"<h2 style='text-align: center; color: {THEME_COLOR}; letter-spacing: 3px;'>KAIROS</h2>", unsafe_allow_html=True)
    st.metric("System State", "Online", delta_color="off")
    st.markdown("---")
    
    selected = option_menu(
        menu_title=None,
        options=["Chat", "Voice", "Vault", "Identity", "Senses"], 
        icons=["chat-heart", "mic", "safe", "fingerprint", "activity"],
        styles={
            "container": {"background-color": "transparent"},
            "icon": {"color": THEME_COLOR, "font-size": "18px"}, 
            "nav-link": {"font-size": "16px", "color": "#E0E0E0"},
            "nav-link-selected": {"background-color": f"{THEME_COLOR}26", "border-left": f"4px solid {THEME_COLOR}"},
        }
    )
    st.markdown("---")
    if st.button("Force Backup to GitHub", use_container_width=True):
        save_chat_history(st.session_state.get('messages', []))
        st.toast("Memories secured", icon="☁️")

# ────────────────────────────────────────────────
# 5. VIEW LOGIC
# ────────────────────────────────────────────────

# --- CHAT TAB ---
if selected == "Chat":
    if "messages" not in st.session_state: st.session_state.messages = load_chat_history()

    for idx, msg in enumerate(st.session_state.messages):
        if msg["role"] not in ["user", "assistant"]: continue
        avatar_icon = "🧬" if msg["role"] == "assistant" else "🕶️"
        with st.chat_message(msg["role"], avatar=avatar_icon):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                if st.button("Replay", key=f"rep_{idx}"): play_audio(msg["content"], idx, autoplay=True)

    prompt = st.chat_input("Message Kairos...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🕶️"): st.markdown(prompt)
        
        with st.chat_message("assistant", avatar="🧬"):
            with st.spinner("Thinking..."):
                stream = get_response(
                    st.session_state.messages,
                    temperature=st.session_state.get('temperature', 1.0),
                    image_path=st.session_state.get('last_image')
                )
                full_res = ""
                holder = st.empty()
                if isinstance(stream, str): full_res = stream
                else:
                    for line in stream.iter_lines():
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8')[6:])
                                full_res += data["choices"][0]["delta"].get("content", "")
                                holder.markdown(full_res + "▌")
                            except: pass
                holder.markdown(full_res)

            update_mood_from_response(full_res)
            should_play = st.session_state.get('auto_play', False)
            play_audio(full_res, len(st.session_state.messages), autoplay=should_play)
            st.session_state.messages.append({"role": "assistant", "content": full_res})
            save_chat_history(st.session_state.messages)

            # Auto-save deep moments to memory vault
            w = classify_memory_weight(prompt, full_res)
            if w == "heavy":
                save_memory_to_vault(st.session_state.messages)
                st.toast("Memory Added", icon="🧠")

            # Clear image context after it's been used
            if 'last_image' in st.session_state:
                del st.session_state['last_image']
                st.toast("Image context cleared")

# --- VOICE MODE ---
elif selected == "Voice":
    st.markdown("<style>.stChatInputContainer {display: none;}</style>", unsafe_allow_html=True)
    st.markdown("<div style='height: 10vh;'></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <div style="display: flex; justify-content: center; align-items: center; flex-direction: column;">
            <div style="
                width: 100px; height: 100px; 
                background-color: {THEME_COLOR}; 
                border-radius: 50%; 
                box-shadow: 0 0 40px {THEME_COLOR}66;
                animation: pulse-glow 3s infinite;">
            </div>
            <h3 style="margin-top: 30px; color: #888;">TAP TO SPEAK</h3>
        </div>
        """, unsafe_allow_html=True)
        
        c_mic_1, c_mic_2, c_mic_3 = st.columns([1,1,1])
        with c_mic_2:
            voice_text = speech_to_text(language='en', start_prompt="🎙️ LISTEN", stop_prompt="🛑 STOP", just_once=True, key='voice_mode_input')

    if voice_text:
        st.info(f"You: {voice_text}")
        if "messages" not in st.session_state: st.session_state.messages = load_chat_history()
        st.session_state.messages.append({"role": "user", "content": voice_text})
        
        with st.spinner("Processing..."):
            response = get_response(st.session_state.messages, temperature=st.session_state.get('temperature', 1.0))
            full_res = ""
            if isinstance(response, str): full_res = response
            else:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8')[6:])
                            full_res += data["choices"][0]["delta"].get("content", "")
                        except: pass
        
        st.markdown(f"<div class='voice-subtitle'>{full_res}</div>", unsafe_allow_html=True)
        play_audio(full_res, len(st.session_state.messages), autoplay=True)
        update_mood_from_response(full_res)
        st.session_state.messages.append({"role": "assistant", "content": full_res})
        save_chat_history(st.session_state.messages)

# --- OTHER TABS ---
elif selected == "Vault":
    st.title("Memory Vault")
    if os.path.exists("vault/memories.txt"):
        with open("vault/memories.txt", "r") as f: memories = f.read().split("\n\n")
        search = st.text_input("Search Memories", key="v_search")
        filtered = [m for m in memories if search.lower() in m.lower()] if search else memories[-10:]
        for m in reversed(filtered):
            with st.expander(f"Memory: {m[:50]}..."): st.write(m.strip())

elif selected == "Identity":
    st.title("Identity Matrix")
    current = load_constitution()
    new_const = st.text_area("Core Personality", current, height=400)
    if st.button("Update Entity"):
        save_constitution(new_const, "Manual Update")
        st.toast("Evolved", icon="✨")

elif selected == "Senses":
    st.title("Senses & Cognition")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔊 Audio Interface")
        st.session_state['auto_play'] = st.toggle("Auto-Play (Chat Mode)", value=st.session_state.get('auto_play', False))
        voice_map = {"Aria (Confident)": "en-US-AriaNeural", "Jenny (Soft)": "en-US-JennyNeural", "Guy (Deep)": "en-US-GuyNeural"}
        v_choice = st.selectbox("Voice Model", list(voice_map.keys()))
        st.session_state['selected_voice'] = voice_map[v_choice]
    with col2:
        st.subheader("👁️ Vision & Mind")
        uploaded = st.file_uploader("Show her something", key="senses_upload")
        if uploaded:
            path = os.path.join("vault", uploaded.name)
            with open(path, "wb") as f: f.write(uploaded.getbuffer())
            st.session_state['last_image'] = path
            st.success("Input received.")
            st.image(path)
        
        st.markdown("---")
        st.session_state['temperature'] = st.slider("Creativity (Temperature)", 0.1, 1.5, 1.0, key='temp_slider')

st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
