import streamlit as st
import openai
import os
import json
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ────────────────────────────────────────────────
# 1. SETUP & AUTH
# ────────────────────────────────────────────────

def get_google_sheet_client():
    """Connects to Google Sheets using Streamlit Secrets."""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # Load credentials from Streamlit secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def save_memory_to_vault(text):
    """Saves a new memory to the 'Memories' tab in Google Sheets."""
    try:
        client = get_google_sheet_client()
        sheet = client.open("Kairos_Memory_Bank").sheet1 # Defaults to first tab
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, text])
    except Exception as e:
        st.error(f"Memory Error: {e}")

def load_memories_from_vault():
    """Reads all memories from the sheet."""
    try:
        client = get_google_sheet_client()
        sheet = client.open("Kairos_Memory_Bank").sheet1
        # Get all records (list of lists)
        records = sheet.get_all_values()
        # Convert to text format for the AI
        memory_text = "\n".join([f"[{row[0]}] {row[1]}" for row in records if len(row) > 1])
        return memory_text
    except:
        return ""

# ────────────────────────────────────────────────
# 2. CORE AI LOGIC
# ────────────────────────────────────────────────

def get_response(messages, temperature=1.0):
    """Generates response using OpenAI/Gemini logic."""
    try:
        client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except:
        return "Error: OpenAI Key missing."

    # 1. Inject Constitution
    system_prompt = load_constitution()
    
    # 2. Inject Memories (Context Window)
    memories = load_memories_from_vault()
    if memories:
        system_prompt += f"\n\n[LONG TERM MEMORY]:\n{memories[-2000:]}" # Limit to last ~2000 chars to save tokens

    # 3. Construct Message Chain
    final_messages = [{"role": "system", "content": system_prompt}]
    
    # Add recent chat history
    for msg in messages:
        if msg["role"] in ["user", "assistant", "system"]:
            final_messages.append(msg)

    try:
        completion = client.chat.completions.create(
            model="gpt-4o", # Or gpt-3.5-turbo
            messages=final_messages,
            temperature=temperature,
            stream=True
        )
        return completion
    except Exception as e:
        return f"Brain Error: {str(e)}"

# ────────────────────────────────────────────────
# 3. UTILITIES (Constitution, History, Mood)
# ────────────────────────────────────────────────

def load_constitution():
    # We can keep Constitution in the sheet too, specifically on Tab 2
    try:
        client = get_google_sheet_client()
        # Ensure a 2nd worksheet exists or create it
        sh = client.open("Kairos_Memory_Bank")
        try:
            worksheet = sh.worksheet("Identity")
        except:
            worksheet = sh.add_worksheet(title="Identity", rows=100, cols=2)
            worksheet.update_cell(1, 1, "Your Core Identity goes here...")
        
        return worksheet.cell(1, 1).value
    except:
        return "You are Kairos. You are helpful and kind."

def save_constitution(text, update_reason="Manual Update"):
    try:
        client = get_google_sheet_client()
        sh = client.open("Kairos_Memory_Bank")
        worksheet = sh.worksheet("Identity")
        worksheet.update_cell(1, 1, text)
    except Exception as e:
        st.error(f"Identity Save Error: {e}")

# Simple Local Fallbacks for things we don't need in Cloud DB yet (like chat history for the session)
def load_chat_history():
    return []

def save_chat_history(messages):
    # In cloud, we rely on session state mostly, or could append to a 'Logs' sheet
    pass

# Placeholder functions to prevent errors in main interface
def reset_memory(): pass
def search_memories(q): return []
def classify_memory_weight(t): return 1
def load_mood_tracker(): return {}
def save_mood_tracker(m): pass
def get_constitution_history(): return []
def load_constitution_version(v): return ""
def append_to_evolution(r): pass
