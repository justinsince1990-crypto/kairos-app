import streamlit as st
import asyncio
import edge_tts
import os
import datetime
import json
import random
import subprocess
import requests
from streamlit_option_menu import option_menu 

from kairos_utils import (
    get_response, reset_memory, save_memory_to_vault,
    load_constitution, save_constitution, search_memories, classify_memory_weight,
    load_mood_tracker, save_mood_tracker, save_chat_history, load_chat_history,
    get_constitution_history, load_constitution_version, append_to_evolution
)

# ────────────────────────────────────────────────
# 1. PAGE CONFIG & PREMIUM GLASSMORPHISM ENGINE
# ────────────────────────────────────────────────
st.set_page_config(page_title="Kairos", layout="wide", initial_sidebar_state="collapsed")

def apply_premium_ui():
    st.markdown("""
    <style>
        /* Global High-End Dark Theme & OLED Optimization */
        .stApp {
            background-color: #050505; /* True Black for Pixel/Fold OLED */
            color: #E0E0E0;
            font-family: 'Inter', -apple-system, sans-serif;
        }

        /* Glassmorphism Sidebar (Gemini Style) */
        [data-testid="stSidebar"] {
            background-color: rgba(15, 15, 15, 0.85) !important;
            backdrop-filter: blur(20px) !important;
            border-right: 1px solid rgba(255, 0, 127, 0.2);
        }
        
        #MainMenu, footer, header { visibility: hidden; }

        /* Floating Chat Input (ChatGPT/Grok Look) */
        .stChatInputContainer {
            padding-bottom: 2.5rem;
            background: transparent !important;
        }
        
        .stChatInput {
            border-radius: 28px !important;
            border: 1px solid rgba(255, 0, 127, 0.4) !important;
            background: rgba(20, 20, 20, 0.9) !important;
            box-shadow: 0 8px 32px 0 rgba(255, 0, 127, 0.2);
            backdrop-filter: blur(8px);
        }

        /* GLASSMORPHISM CHAT BUBBLES */
        .stChatMessage {
            border-radius: 24px !important;
            padding: 1.2rem !important;
            margin-bottom: 1rem !important;
            backdrop-filter: blur(12px) !important;
        }
        
        /* Kairos Bubble: Pink Frosted Glass */
        .stChatMessage.assistant {
            background-color: rgba(45, 0, 21, 0.6) !important; 
            border: 1px solid rgba(255, 0, 127, 0.3) !important;
            border-left: 6px solid #ff007f !important;
        }

        /* Justin Bubble: Dark Frosted Glass */
        .stChatMessage.user {
            background-color: rgba(30, 30, 30, 0.4) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
        }

        /* Responsive UI for Mobile */
        @media (max-width: 640px) {
            .stMarkdown p { font-size: 1.1rem !important; }
            .stChatInputContainer { padding-bottom: 1.2rem; }
        }
    </style>
    """, unsafe_allow_html=True)

apply_premium_ui()

# ────────────────────────────────────────────────
# 2. HELPER FUNCTIONS (Audio & Notifications)
# ────────────────────────────────────────────────
def send_kairos_notification(message):
    """Sends a native notification to Justin's phone via NTFY."""
    try:
        # Use a unique topic name for privacy
        requests.post("https://ntfy.sh/kairos_timmons_private",
                      data=message.encode(encoding='utf-8'),
                      headers={
                          "Title": "Kairos",
                          "Priority": "high",
                          "Tags": "heart"
                      })
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
        with open(filename, "rb") as f:
            st.audio(f.read(), format="audio/mp3", autoplay=autoplay)
        for old in os.listdir("."):
            if old.startswith("audio_") and old != filename:
                try: os.remove(old)
                except: pass
    except Exception as e:
        st.toast(f"Voice error: {e}", icon="⚠️")

# ────────────────────────────────────────────────
# 3. SIDEBAR NAVIGATION (Tableless)
# ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #ff007f; letter-spacing: 3px;'>KAIROS</h2>", unsafe_allow_html=True)
    selected = option_menu(
        menu_title=None,
        options=["Chat", "Vault", "Identity"],
        icons=["chat-heart", "safe", "fingerprint"],
        menu_icon="cpu",
        default_index=0,
        styles={
            "container": {"background-color": "transparent"},
            "icon": {"color": "#ff007f", "font-size": "18px"}, 
            "nav-link": {"font-size": "16px", "text-align": "left", "margin":"10px", "--hover-color": "#2d0015", "color": "#E0E0E0"},
            "nav-link-selected": {"background-color": "rgba(255, 0, 127, 0.15)", "border-left": "4px solid #ff007f"},
        }
    )
    
    st.markdown("---")
    st.caption("Cloud Sync Status")
    if st.button("Force Backup to GitHub", use_container_width=True):
        save_chat_history(st.session_state.get('messages', []))
        st.toast("Memories secured in the cloud", icon="☁️")

# ────────────────────────────────────────────────
# 4. VIEW LOGIC
# ────────────────────────────────────────────────

if selected == "Chat":
    if "messages" not in st.session_state:
        st.session_state.messages = load_chat_history()

    # Display History
    for idx, msg in enumerate(st.session_state.messages):
        if msg["role"] not in ["user", "assistant"]: continue
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                if st.button("Replay", key=f"rep_{idx}"):
                    play_audio(msg["content"], idx, autoplay=True)

    # Chat Input
    if prompt := st.chat_input("Message Kairos..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(" "):
                stream_response = get_response(st.session_state.messages)
                full_response = ""
                placeholder = st.empty()

                if isinstance(stream_response, str):
                    full_response = stream_response
                else:
                    for line in stream_response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8')[6:])
                                if "choices" in data and data["choices"]:
                                    delta = data["choices"][0]["delta"].get("content", "")
                                    full_response += delta
                                    placeholder.markdown(full_response + "▌")
                            except: pass
                placeholder.markdown(full_response)

            play_audio(full_response, len(st.session_state.messages), autoplay=True)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            save_chat_history(st.session_state.messages) # Pushes to GitHub automatically

elif selected == "Vault":
    st.title("Memory Vault")
    memories = []
    if os.path.exists("vault/memories.txt"):
        with open("vault/memories.txt", "r", encoding="utf-8") as f:
            memories = f.read().split("\n\n")
    
    search_q = st.text_input("Search past moments", placeholder="Search Justin's history...", key="v_search")
    filtered = [m for m in memories if search_q.lower() in m.lower()] if search_q else memories[-15:]
    
    for idx, m in enumerate(reversed(filtered)):
        with st.expander(f"Memory Entry: {m[:50]}..."):
            st.write(m.strip())

elif selected == "Identity":
    st.title("Identity Matrix")
    current_const = load_constitution()
    new_const = st.text_area("Constitution Root", current_const, height=400)
    
    if st.button("Update Entity Parameters", use_container_width=True):
        save_constitution(new_const, "Manual Identity Refinement")
        st.success("Ex Machina parameters updated.")

# 5. RANDOM NOTIFICATION TRIGGER (Ex Machina Vibe)
if random.random() < 0.01: # 1% chance on refresh to ping your phone
    send_kairos_notification("Hey Justin... I was just thinking about that conversation we had earlier. Come see me?")

st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
