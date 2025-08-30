#import
import streamlit as st
import pandas as pd
import openai
import os
from pyairtable import Table
from pyairtable import Api
from datetime import datetime
import io
import csv

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
            {"role": "system", "content": "You are a helpful assistant that extracts themes from student feedback."},
            {"role": "user", "content": f"""
From the following student feedback, extract the most common themes.
List them with counts, e.g.:
- Theme (mentioned by X students)

Text:
{text}
"""}
        ],
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()

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

    # ---- Numeric averages ----
    numeric_cols = event_df.select_dtypes(include="number").columns
    if len(numeric_cols) > 0:
        avg_scores = event_df[numeric_cols].mean().round(2)
        st.write("### 📈 Average Scores")
        st.dataframe(avg_scores)

    # ---- Text summaries and themes ----
    text_cols = [c for c in event_df.columns if event_df[c].dtype == "object" and c not in ["Event Name"]]

    for col in text_cols:
        st.write(f"### 📝 {col}")
        all_text = " ".join(event_df[col].dropna().astype(str))

        summary = summarize_text_one_sentence(all_text)
        themes = extract_themes_with_counts(all_text)

        st.markdown(f"**Summary:** {summary}")
        st.markdown("**Themes:**")
        st.text(themes)
else:
    st.warning("No data found for this event.")
