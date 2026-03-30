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

def limit_text_length(text, max_chars=8000):
    return text[:max_chars]

def safe_openai_call(func, *args, retries=3, base_delay=2, **kwargs):
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except openai.RateLimitError:
            wait = base_delay * (2 ** i) + random.uniform(0, 1)
            time.sleep(wait)
    return "⚠️ Skipped (rate limit)"

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

# ============ FILTERS ============

# Event filter
if "Event Start (from Event) 2" in table_df.columns:
    table_df["Event Start (from Event) 2"] = pd.to_datetime(
        table_df["Event Start (from Event) 2"], errors="coerce"
    )
    event_info = table_df[["Events", "Event Start (from Event) 2"]] \
        .dropna(subset=["Events"]).drop_duplicates() \
        .sort_values("Event Start (from Event) 2", ascending=False)
    event_names = event_info["Events"].tolist()
else:
    event_names = sorted(table_df["Events"].dropna().unique())

selected_events = st.multiselect("Select Event(s)", event_names)

# Event Type filter
if "Type (from Event) 2" in table_df.columns:
    table_df["Type (from Event) 2"] = table_df["Type (from Event) 2"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) else str(x) if pd.notna(x) else None
    )
    event_types = sorted(table_df["Type (from Event) 2"].dropna().unique())
    selected_types = st.multiselect("Select Event Type(s)", event_types)
else:
    selected_types = []

# Program Year filter
if "Program Year (from Event)" in table_df.columns:
    table_df["Program Year (from Event)"] = table_df["Program Year (from Event)"].astype(str)
    program_years = sorted(table_df["Program Year (from Event)"].dropna().unique())
    selected_years = st.multiselect("Select Program Year(s)", program_years)
else:
    selected_years = []

# Apply filters
event_df = table_df.copy()

if selected_events:
    event_df = event_df[event_df["Events"].isin(selected_events)]
if selected_types:
    event_df = event_df[event_df["Type (from Event) 2"].isin(selected_types)]
if selected_years:
    event_df = event_df[event_df["Program Year (from Event)"].isin(selected_years)]

# ============ QUESTIONS ============
numeric_questions = [
    "Question 1- Net Promoter",
    "Question 2- Engaging",
    "Question 6- Program Specific #1",
    "Question 7- Program Specific #2",
    "Question 8",
    "Question 9",
]

text_questions = [
    "Question 3- learned",
    "Question 4b- Liked best",
    "Question 5- Suggestions or comments",
    "Question 10- Program Specific #5 Open Text",
]

# ============ MAIN PROCESS ============
if not event_df.empty and (selected_events or selected_types or selected_years):

    st.subheader("📌 Summary Results")

    with st.spinner("Analyzing feedback..."):

        results = []

        # =============================
        # GLOBAL TEXT PROCESSING (FAST + SAFE)
        # =============================
        summary_results = {}
        theme_results = {}

        for col in text_questions:
            if col in event_df.columns:
                # sample to prevent overload
                sampled = event_df[col].dropna()
                sampled = sampled.sample(n=min(50, len(sampled)), random_state=42)

                all_text = " ".join(sampled.astype(str))
                all_text = limit_text_length(all_text)
                text_hash = hash_text(all_text)

                summary = safe_openai_call(summarize_text_cached, text_hash, all_text)
                theme = safe_openai_call(extract_themes_cached, text_hash, all_text)

                summary_results[col] = summary
                theme_results[col] = theme

                time.sleep(1)  # throttle

        # =============================
        # PER EVENT LOOP (NO API CALLS)
        # =============================
        for event in event_df["Events"].dropna().unique():
            event_data = event_df[event_df["Events"] == event]

            # Numeric averages
            for col in numeric_questions:
                if col in event_data.columns:
                    numeric_series = event_data[col].dropna().apply(extract_leading_number)
                    avg_val = round(numeric_series.mean(), 2) if not numeric_series.empty else ""

                    results.append({
                        "Event": event,
                        "Question": col + "_Average",
                        "Value": avg_val
                    })

            # Summaries
            for col in text_questions:
                if col in summary_results:
                    results.append({
                        "Event": event,
                        "Question": col + "_Summary",
                        "Value": summary_results[col]
                    })

            # Themes
            for col in text_questions:
                if col in theme_results:
                    results.append({
                        "Event": event,
                        "Question": col + "_Themes",
                        "Value": theme_results[col]
                    })

    results_df = pd.DataFrame(results)

    st.write("### 📊 Student Feedback Summary")
    st.data_editor(results_df, use_container_width=True, hide_index=True)

    st.write("### 📝 Raw Feedback")
    st.dataframe(event_df, use_container_width=True)

else:
    st.info("ℹ️ Please select at least one filter to view results.")