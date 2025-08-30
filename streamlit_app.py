import streamlit as st
import pandas as pd
from pyairtable import Table
import re
import openai

# Airtable setup
AIRTABLE_API_KEY = st.secrets["AIRTABLE_API_KEY"]
BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
TABLE_NAME = "Program Eval Data"

table = Table(AIRTABLE_API_KEY, BASE_ID, TABLE_NAME)

# Question mappings
numeric_questions = {
    "Question 1- Net Promoter": "Q1_Avg",
    "Question 2- Engaging": "Q2_Avg"
}

text_summary_questions = {
    "Question 3- learned": "Q3_Summary",
    "Question 4b- Liked best": "Q4b_Summary",
    "Question 4c- Improvement": "Q4c_Summary"
}

text_theme_questions = {
    "Question 3- learned": "Q3_Themes",
    "Question 4b- Liked best": "Q4b_Themes",
    "Question 4c- Improvement": "Q4c_Themes"
}

# ========== Helpers ==========
def extract_leading_number(text):
    if pd.isna(text):
        return None
    match = re.match(r"(\d+)", str(text))
    return int(match.group(1)) if match else None

def summarize_text_one_sentence(text):
    if not text.strip():
        return ""
    # Fallback simple summary
    if len(text.split()) < 30:
        return text
    return " ".join(text.split()[:30]) + "..."

def extract_themes_with_counts(text):
    words = text.split()
    if not words:
        return ""
    # Simple keyword count
    counts = pd.Series(words).value_counts().head(3)
    themes = [f"- {word} ({count} mentions)" for word, count in counts.items()]
    return "\n".join(themes)

# ========== Streamlit App ==========
st.title("📊 Program Evaluation Dashboard")

# Fetch all records from Airtable
records = table.all()
df = pd.DataFrame([r["fields"] for r in records])

# Event selection
event_options = df["Event Name"].dropna().unique()
selected_event = st.selectbox("Select an event", event_options)

if selected_event:
    event_df = df[df["Event Name"] == selected_event]

    # ========== Build results (two-column format) ==========
    results = []

    # Numeric
    for col, new_col in numeric_questions.items():
        if col in event_df.columns:
            numeric_series = event_df[col].dropna().apply(extract_leading_number)
            avg_val = round(numeric_series.mean(), 2) if not numeric_series.empty else ""
            results.append({
                "Question": col,
                "Value": avg_val
            })

    # Summaries
    for col, new_col in text_summary_questions.items():
        if col in event_df.columns:
            all_text = " ".join(event_df[col].dropna().astype(str))
            summary = summarize_text_one_sentence(all_text)
            results.append({
                "Question": f"{col} _summary",
                "Value": summary
            })

    # Themes
    for col, new_col in text_theme_questions.items():
        if col in event_df.columns:
            all_text = " ".join(event_df[col].dropna().astype(str))
            themes = extract_themes_with_counts(all_text)
            results.append({
                "Question": f"{col} _theme",
                "Value": themes
            })

    # Convert to DataFrame (two column)
    results_df = pd.DataFrame(results, columns=["Question", "Value"])

    # Show summary
    st.write("### 📊 Question 1–10 Summary (Readable Format)")
    st.dataframe(results_df, use_container_width=True)

    # ========== Raw Feedback ==========
    st.write("### 📝 Raw Feedback (from Airtable)")
    feedback_cols = list(text_summary_questions.keys()) + list(text_theme_questions.keys())

    for col in feedback_cols:
        if col in event_df.columns:
            st.subheader(col)
            for feedback in event_df[col].dropna().tolist():
                st.write(f"- {feedback}")
