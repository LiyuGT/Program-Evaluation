# ============ IMPORTS ============
import streamlit as st
import pandas as pd
import openai
import os
import re
from pyairtable import Api

# ============ CONFIG ============
# Safe secrets handling
try:
    APP_PIN = st.secrets["APP_PIN"]
except Exception:
    APP_PIN = "1234"

# API keys (safe fallback)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or (
    st.secrets["OPENAI_API_KEY"] if "OPENAI_API_KEY" in st.secrets else None
)

AIRTABLE_PERSONAL_TOKEN = os.getenv("AIRTABLE_PERSONAL_TOKEN") or (
    st.secrets["AIRTABLE_PERSONAL_TOKEN"] if "AIRTABLE_PERSONAL_TOKEN" in st.secrets else None
)

openai.api_key = OPENAI_API_KEY

BASE_ID = "app3GAOlTLaNgZ5u5"
TABLE = "Program Eval Data"

# ============ PIN LOCK ============
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

# ============ FUNCTIONS ============

@st.cache_data(show_spinner=False)
def summarize_text_one_sentence(text, max_tokens=80):
    if not text or not str(text).strip():
        return ""

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Summarize student feedback in one concise sentence."},
            {"role": "user", "content": text},
        ],
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


@st.cache_data(show_spinner=False)
def extract_themes_with_counts(text, max_tokens=200):
    if not text or not str(text).strip():
        return ""

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Extract the most common themes from feedback with counts, in bullet format."},
            {"role": "user", "content": f"""
From the following student feedback, extract and list the **main themes with counts**, formatted like:
- <theme> (mentioned by X students)

Text:
{text}
"""}
        ],
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def extract_leading_number(value):
    if pd.isna(value):
        return None
    match = re.match(r"(\d+)", str(value))
    return int(match.group(1)) if match else None


# ============ MAPPINGS ============
numeric_questions = {
    "Question 1- Net Promoter": "Question 1- Net Promoter_num",
    "Question 2- Engaging": "Question 2- Engaging_num",
    "Question 6- Program Specific #1": "Question 6- Program Specific #1_num",
    "Question 7- Program Specific #2": "Question 7- Program Specific #2_num",
    "Question 8": "Question 8_num",
    "Question 9": "Question 9_num",
}

text_summary_questions = {
    "Question 3- learned": "Question 3- learned_summary",
    "Question 4b- Liked best": "Question 4b- Liked best_summary",
    "Question 5- Suggestions or comments": "Question 5- Suggestions or comments_summary",
    "Question 10- Program Specific #5 Open Text": "Question 10- Program Specific #5 Open Text_summary",
}

text_theme_questions = {
    "Question 3- learned": "Question 3- learned_themes",
    "Question 4b- Liked best": "Question 4b- Liked best_themes",
    "Question 5- Suggestions or comments": "Question 5- Suggestions or comments_themes",
    "Question 10- Program Specific #5 Open Text": "Question 10- Program Specific #5 Open Text_Themes",
}

# ============ FILTERS ============
selected_events = st.multiselect("Select Event(s)", sorted(table_df["Events"].dropna().unique()))
selected_types = st.multiselect("Select Event Type(s)", sorted(table_df["Type (from Event) 2"].dropna().unique())) if "Type (from Event) 2" in table_df.columns else []
selected_years = st.multiselect("Select Program Year(s)", sorted(table_df["Program Year (from Event)"].dropna().astype(str).unique())) if "Program Year (from Event)" in table_df.columns else []

event_df = table_df.copy()

if selected_events:
    event_df = event_df[event_df["Events"].isin(selected_events)]
if selected_types:
    event_df = event_df[event_df["Type (from Event) 2"].isin(selected_types)]
if selected_years:
    event_df = event_df[event_df["Program Year (from Event)"].isin(selected_years)]

# ============ MAIN EXECUTION BUTTON ============
if st.button("🚀 Generate Summary"):

    if not event_df.empty:
        results = []

        for event in event_df["Events"].dropna().unique():
            event_data = event_df[event_df["Events"] == event]

            # Numeric
            for col in numeric_questions:
                if col in event_data.columns:
                    numeric_series = event_data[col].dropna().apply(extract_leading_number)
                    avg_val = round(numeric_series.mean(), 2) if not numeric_series.empty else ""
                    results.append({"Event": event, "Question": col + "_Average", "Value": avg_val})

            # Summaries
            for col in text_summary_questions:
                if col in event_data.columns:
                    all_text = " ".join(event_data[col].dropna().astype(str))
                    summary = summarize_text_one_sentence(all_text)
                    results.append({"Event": event, "Question": col + "_Summary", "Value": summary})

            # Themes
            for col in text_theme_questions:
                if col in event_data.columns:
                    all_text = " ".join(event_data[col].dropna().astype(str))
                    themes = extract_themes_with_counts(all_text)
                    results.append({"Event": event, "Question": col + "_Themes", "Value": themes})

        results_df = pd.DataFrame(results)

        st.write("### 📊 Student Feedback Summary")
        st.dataframe(results_df, use_container_width=True)

        # Raw data
        st.write("### 📝 Raw Student Feedback")
        st.dataframe(event_df, use_container_width=True)

    else:
        st.warning("No data found for selected filters.")