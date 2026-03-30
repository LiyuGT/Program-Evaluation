# import
import streamlit as st
import pandas as pd
import openai
import os
import re
import time
import hashlib
import random
from pyairtable import Api

# ============ CONFIG ============
AIRTABLE_PERSONAL_TOKEN = os.getenv("AIRTABLE_PERSONAL_TOKEN")
BASE_ID = "app3GAOlTLaNgZ5u5"
TABLE = "Program Eval Data"
openai.api_key = os.getenv("OPENAI_API_KEY")

# ============ PIN LOCK ============
try:
    APP_PIN = st.secrets["APP_PIN"]
except:
    APP_PIN = "1234"

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 Secure GenOne Program Eval Dashboard")
    pin_input = st.text_input("Enter PIN", type="password")
    if st.button("Unlock"):
        if pin_input == APP_PIN:
            st.session_state["authenticated"] = True
            st.success("✅ Access granted")
            st.rerun()
        else:
            st.error("❌ Wrong PIN. Try again.")
    st.stop()

# ============ STREAMLIT APP ============
st.set_page_config(layout="wide")
st.title("📊 Program Evaluation Dashboard")

# ============ AIRTABLE CONNECTION ============
api = Api(AIRTABLE_PERSONAL_TOKEN)
table = api.table(BASE_ID, TABLE)
records = table.all(view="All Responses")
table_df = pd.DataFrame([record["fields"] for record in records])

# ============ HELPERS ============

def hash_text(text):
    return hashlib.md5(text.encode()).hexdigest()

def safe_openai_call(func, *args, retries=5, base_delay=2, **kwargs):
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except openai.RateLimitError:
            wait = base_delay * (2 ** i) + random.uniform(0, 1)
            time.sleep(wait)
        except Exception as e:
            raise e
    return "⚠️ API failed after retries"

@st.cache_data(show_spinner=False)
def summarize_text_cached(text_hash, text):
    if not text.strip():
        return ""
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Summarize student feedback in one concise sentence."},
            {"role": "user", "content": text},
        ],
        max_tokens=80,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()

@st.cache_data(show_spinner=False)
def extract_themes_cached(text_hash, text):
    if not text.strip():
        return ""
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Extract the most common themes with counts."},
            {"role": "user", "content": f"""
Extract themes with counts:
- <theme> (mentioned by X students)

Text:
{text}
"""}
        ],
        max_tokens=200,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()

def extract_leading_number(value):
    if pd.isna(value):
        return None
    match = re.match(r"(\d+)", str(value))
    return int(match.group(1)) if match else None

# ========== Question mappings ==========
numeric_questions = {
    "Question 1- Net Promoter": "Question 1- Net Promoter_num",
    "Question 2- Engaging": "Question 2- Engaging_num",
    "Question 6- Program Specific #1": "Question 6- Program Specific #1_num",
    "Question 7- Program Specific #2": "Question 7- Program Specific #2_num",
    "Question 8": "Question 8_num",
    "Question 9": "Question 9_num",
}

text_summary_questions = [
    "Question 3- learned",
    "Question 4b- Liked best",
    "Question 5- Suggestions or comments",
    "Question 10- Program Specific #5 Open Text",
]

text_theme_questions = text_summary_questions.copy()

# ============ FILTERS ============
event_names = sorted(table_df["Events"].dropna().unique())
selected_events = st.multiselect("Select Event(s)", event_names)

event_df = table_df.copy()
if selected_events:
    event_df = event_df[event_df["Events"].isin(selected_events)]

# ============ PROCESS ============
if not event_df.empty and selected_events:

    st.subheader("📌 Summary for Selected Events")

    results = []

    # =============================
    # 🔥 GLOBAL TEXT PROCESSING (KEY FIX)
    # =============================
    summary_results = {}
    theme_results = {}

    for col in text_summary_questions:
        if col in event_df.columns:
            all_text = " ".join(event_df[col].dropna().astype(str))
            text_hash = hash_text(all_text)

            try:
                summary = safe_openai_call(summarize_text_cached, text_hash, all_text)
                time.sleep(1)  # throttle
            except:
                summary = "⚠️ Summary unavailable"

            summary_results[col] = summary

    for col in text_theme_questions:
        if col in event_df.columns:
            all_text = " ".join(event_df[col].dropna().astype(str))
            text_hash = hash_text(all_text)

            try:
                themes = safe_openai_call(extract_themes_cached, text_hash, all_text)
                time.sleep(1)
            except:
                themes = "⚠️ Themes unavailable"

            theme_results[col] = themes

    # =============================
    # PER EVENT LOOP (NO API CALLS)
    # =============================
    for event in event_df["Events"].dropna().unique():
        event_data = event_df[event_df["Events"] == event]

        # Numeric
        for col in numeric_questions.keys():
            if col in event_data.columns:
                numeric_series = event_data[col].dropna().apply(extract_leading_number)
                avg_val = round(numeric_series.mean(), 2) if not numeric_series.empty else ""

                results.append({
                    "Event": event,
                    "Question": col + "_Average",
                    "Value": avg_val
                })

        # Summaries (reuse global)
        for col in text_summary_questions:
            if col in summary_results:
                results.append({
                    "Event": event,
                    "Question": col + "_Summary",
                    "Value": summary_results[col]
                })

        # Themes (reuse global)
        for col in text_theme_questions:
            if col in theme_results:
                results.append({
                    "Event": event,
                    "Question": col + "_Themes",
                    "Value": theme_results[col]
                })

    results_df = pd.DataFrame(results)

    st.write("### 📊 Student Feedback Summary")
    st.data_editor(results_df, use_container_width=True, hide_index=True, disabled=True)

    # Raw data
    st.write("### 📝 Raw Feedback")
    st.dataframe(event_df, use_container_width=True)

else:
    st.info("ℹ️ Please select at least one event.")