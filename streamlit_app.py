#import
import streamlit as st
import pandas as pd
import openai
import os
import re
from pyairtable import Api

# ============ CONFIG ============
AIRTABLE_PERSONAL_TOKEN = os.getenv("AIRTABLE_PERSONAL_TOKEN")
BASE_ID = "app3GAOlTLaNgZ5u5"
TABLE = "Program Eval Data"
openai.api_key = os.getenv("OPENAI_API_KEY")

# ============ AIRTABLE CONNECTION ============
api = Api(AIRTABLE_PERSONAL_TOKEN)
table = api.table(BASE_ID, TABLE)
records = table.all(view="All Responses")
table_df = pd.DataFrame([record["fields"] for record in records])

# ============ FUNCTIONS ============
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
    """Extracts leading numeric value from strings like '5-Definitely 😊 👍'"""
    if pd.isna(value):
        return None
    match = re.match(r"(\d+)", str(value))
    return int(match.group(1)) if match else None

# ============ STREAMLIT APP ============
st.set_page_config(layout="wide")
st.title("📊 Program Evaluation Dashboard")

# Dropdown for event selection
event_names = sorted(table_df["Events"].dropna().unique())
selected_event = st.selectbox("Select an Event", event_names)

# Filter data
event_df = table_df[table_df["Events"] == selected_event]

if not event_df.empty:
    st.subheader(f"📌 Summary for: {selected_event}")

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
    }

    text_theme_questions = {
        "Question 3- learned": "Question 3- learned_themes",
        "Question 4b- Liked best": "Question 4b- Liked best_themes",
        "Question 5- Suggestions or comments": "Question 5- Suggestions or comments_themes",
    }

    # ========== Build one row result ==========
    row_result = {"Event Name": selected_event}

    # Numeric
    for col, new_col in numeric_questions.items():
        if col in event_df.columns:
            numeric_series = event_df[col].dropna().apply(extract_leading_number)
            if not numeric_series.empty:
                row_result[new_col] = round(numeric_series.mean(), 2)
            else:
                row_result[new_col] = ""

    # Summaries
    for col, new_col in text_summary_questions.items():
        if col in event_df.columns:
            all_text = " ".join(event_df[col].dropna().astype(str))
            row_result[new_col] = summarize_text_one_sentence(all_text)

    # Themes
    for col, new_col in text_theme_questions.items():
        if col in event_df.columns:
            all_text = " ".join(event_df[col].dropna().astype(str))
            row_result[new_col] = extract_themes_with_counts(all_text)

    # Convert to DataFrame (single row)
    results_df = pd.DataFrame([row_result])

    # Show results
    st.write("### 📊 Question 1–10 Summary")
    st.dataframe(results_df, use_container_width=True)

    # ========== Raw Feedback Section ==========
    st.write("### 📝 Raw Student Feedback")
    feedback_cols = [c for c in event_df.columns if c.startswith("Question")]
    st.dataframe(event_df[["Events"] + feedback_cols], use_container_width=True)

else:
    st.warning("No data found for this event.")
