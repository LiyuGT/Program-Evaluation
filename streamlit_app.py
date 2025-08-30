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
            {"role": "system", "content": "Extract the most common theme from feedback with counts."},
            {"role": "user", "content": f"""
From the following student feedback, extract the **most common theme only**, formatted like:
<theme> (mentioned by X students)

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

    # Limit to Questions 1–10
    question_cols = [col for col in event_df.columns if col.startswith("Question") and any(col.startswith(f"Question {i}") for i in range(1, 11))]

    # Convert Likert-style responses to numeric for any column like "5-Definitely..."
    for col in question_cols:
        if event_df[col].dtype == "object" and event_df[col].str.match(r"^\d+").any():
            event_df[col] = event_df[col].apply(extract_leading_number)

    results = []
    for col in question_cols:
        if pd.api.types.is_numeric_dtype(event_df[col]):
            avg_val = round(event_df[col].mean(), 2)
            results.append({"Question": col, "Average": avg_val, "Summary": "", "Themes": ""})
        else:
            all_text = " ".join(event_df[col].dropna().astype(str))
            summary = summarize_text_one_sentence(all_text)
            themes = extract_themes_with_counts(all_text)
            results.append({"Question": col, "Average": "", "Summary": summary, "Themes": themes})

    results_df = pd.DataFrame(results).set_index("Question")

    # Show results in row format
    st.write("### 📊 Question 1–10 Summary")
    st.dataframe(results_df, use_container_width=True)

else:
    st.warning("No data found for this event.")
