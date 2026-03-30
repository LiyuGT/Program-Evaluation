# import
import streamlit as st
import pandas as pd
import openai
import os
import re
import time
from pyairtable import Api
from openai.error import RateLimitError

# ============ CONFIG ============
AIRTABLE_PERSONAL_TOKEN = os.getenv("AIRTABLE_PERSONAL_TOKEN")
BASE_ID = "app3GAOlTLaNgZ5u5"
TABLE = "Program Eval Data"
openai.api_key = os.getenv("OPENAI_API_KEY")

# ============ PIN LOCK ============
try:
    APP_PIN = st.secrets["APP_PIN"]
except:
    APP_PIN = "1234"  # fallback

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
    st.stop()  # ⛔ stop here if not authenticated

# ============ STREAMLIT APP ============
st.set_page_config(layout="wide")
st.title("📊 Program Evaluation Dashboard")

# ============ AIRTABLE CONNECTION ============
api = Api(AIRTABLE_PERSONAL_TOKEN)
table = api.table(BASE_ID, TABLE)
records = table.all(view="All Responses")
table_df = pd.DataFrame([record["fields"] for record in records])

# ============ FUNCTIONS ============
def safe_openai_call(func, *args, retries=3, delay=5, **kwargs):
    """Retry OpenAI call on rate limit errors"""
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except RateLimitError:
            if i < retries - 1:
                time.sleep(delay)
            else:
                raise

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
From the following student feedback, extract and list the main themes with counts, formatted like:
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
    """Extracts leading numeric value from strings like '5-Definitely 😊 👍'"""
    if pd.isna(value):
        return None
    match = re.match(r"(\d+)", str(value))
    return int(match.group(1)) if match else None

# ========== Define question mapping ==========
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

# ============ EVENT MULTI-SELECT ============
if "Event Start (from Event) 2" in table_df.columns:
    table_df["Event Start (from Event) 2"] = pd.to_datetime(table_df["Event Start (from Event) 2"], errors="coerce")
    event_info = table_df[["Events", "Event Start (from Event) 2"]].dropna(subset=["Events"]).drop_duplicates()
    event_info = event_info.sort_values("Event Start (from Event) 2", ascending=False)
    event_names = event_info["Events"].tolist()
else:
    st.warning("⚠️ No 'Event Start (from Event) 2' column found in Airtable data.")
    event_names = sorted(table_df["Events"].dropna().unique())

selected_events = st.multiselect("Select Event(s)", event_names, placeholder="Choose Event(s)")

# ============ EVENT TYPE MULTI-SELECT ============
if "Type (from Event) 2" in table_df.columns:
    table_df["Type (from Event) 2"] = table_df["Type (from Event) 2"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) else str(x) if pd.notna(x) else None
    )
    event_types = sorted(table_df["Type (from Event) 2"].dropna().unique())
    selected_types = st.multiselect("Select Event Type(s)", event_types, placeholder="Choose Event Type(s)")
else:
    st.warning("⚠️ No 'Type (from Event) 2' column found in Airtable data.")
    selected_types = []

# ============ PROGRAM YEAR MULTI-SELECT ============
if "Program Year (from Event)" in table_df.columns:
    table_df["Program Year (from Event)"] = table_df["Program Year (from Event)"].astype(str)
    program_years = sorted(table_df["Program Year (from Event)"].dropna().unique())
    selected_years = st.multiselect("Select Program Year(s)", program_years, placeholder="Choose Program Year(s)")
else:
    st.warning("⚠️ No 'Program Year (from Event)' column found in Airtable data.")
    selected_years = []

# ============ FLEXIBLE FILTERING ============
event_df = table_df.copy()
if selected_events:
    event_df = event_df[event_df["Events"].isin(selected_events)]
if selected_types:
    event_df = event_df[event_df["Type (from Event) 2"].isin(selected_types)]
if selected_years:
    event_df = event_df[event_df["Program Year (from Event)"].isin(selected_years)]

# ============ SUMMARY ============
if not event_df.empty and (selected_events or selected_types or selected_years):
    filter_summary = []
    if selected_events:
        filter_summary.append(f"Events: {', '.join(selected_events)}")
    if selected_types:
        filter_summary.append(f"Types: {', '.join(selected_types)}")
    if selected_years:
        filter_summary.append(f"Program Years: {', '.join(selected_years)}")

    st.subheader("📌 Summary for: " + (" | ".join(filter_summary)))
    results = []

    # Loop by event (or event type / year)
    for event in event_df["Events"].dropna().unique():
        event_data = event_df[event_df["Events"] == event]

        # Numeric averages
        for col in numeric_questions.keys():
            if col in event_data.columns:
                numeric_series = event_data[col].dropna().apply(extract_leading_number)
                avg_val = round(numeric_series.mean(), 2) if not numeric_series.empty else ""
                results.append({
                    "Event": event,
                    "Question": col + "_Average",
                    "Value": avg_val
                })

        # Summaries (batched)
        for col in text_summary_questions.keys():
            if col in event_data.columns:
                all_text = " ".join(event_data[col].dropna().astype(str))
                summary = safe_openai_call(summarize_text_one_sentence, all_text)
                results.append({
                    "Event": event,
                    "Question": col + "_Summary",
                    "Value": summary
                })

        # Themes (batched)
        for col in text_theme_questions.keys():
            if col in event_data.columns:
                all_text = " ".join(event_data[col].dropna().astype(str))
                themes = safe_openai_call(extract_themes_with_counts, all_text)
                results.append({
                    "Event": event,
                    "Question": col + "_Themes",
                    "Value": themes
                })

    results_df = pd.DataFrame(results)[["Event", "Question", "Value"]]

    st.write("### 📊 Student Feedback Summary (by Event)")
    st.data_editor(
        results_df,
        use_container_width=True,
        column_config={
            "Event": st.column_config.TextColumn("Event", width=150),
            "Question": st.column_config.TextColumn("Question", width=160),
            "Value": st.column_config.TextColumn("Value", width=750),
        },
        hide_index=True,
        disabled=True
    )

    # Raw Feedback
    st.write("### 📝 Raw Student Feedback")
    feedback_cols = [c for c in event_df.columns if c.startswith("Question")]
    display_cols = ["Program Year (from Event)", "Scholars (from Scholars)", "Type (from Event) 2", "Events"] + feedback_cols
    display_cols = [c for c in display_cols if c in event_df.columns]
    st.dataframe(event_df[display_cols], use_container_width=True)

else:
    if not selected_events and not selected_types and not selected_years:
        st.info("ℹ️ Please select a filter (Event, Event Type, or Program Year) to view results.")
    else:
        st.warning("No data found for the selected filters.")