import streamlit as st
import pandas as pd
import re

# ================== CONFIG ==================
st.set_page_config(layout="wide")

# Define which questions are numeric vs summary vs theme
numeric_questions = {
    "Question 1- Net Promoter": "Net Promoter Score",
    "Question 2- Engaging": "Engaging Score"
}

text_summary_questions = {
    "Question 3- learned": "What students learned",
    "Question 4b- Liked best": "Liked best",
    "Question 5- Suggestions or comments": "Suggestions or comments"
}

text_theme_questions = {
    "Question 3- learned": "Learned Themes",
    "Question 4b- Liked best": "Liked Best Themes",
    "Question 5- Suggestions or comments": "Suggestions Themes"
}

# ============== HELPER FUNCTIONS =================
def extract_leading_number(text):
    """Extract first number from string (for ratings like '5 - Very Engaging')"""
    if pd.isna(text):
        return None
    match = re.match(r"(\d+)", str(text).strip())
    return int(match.group(1)) if match else None

def summarize_text_one_sentence(text):
    """Fake summarizer (replace with LLM call if needed)"""
    if not text.strip():
        return ""
    return f"Summary of {len(text.split())} words"

def extract_themes_with_counts(text):
    """Extract simple themes by splitting words >4 chars and counting"""
    if not text.strip():
        return ""
    words = re.findall(r"\w+", text.lower())
    freq = {}
    for w in words:
        if len(w) > 4:
            freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:5]
    return ", ".join([f"{w} ({c})" for w, c in top])

# ============== LOAD DATA =================
@st.cache_data
def load_data():
    # Replace with your Airtable/CSV/DB call
    df = pd.read_csv("event_feedback.csv")
    return df

event_df = load_data()

# ============== FILTERS =================
st.sidebar.header("Filters")

all_events = sorted(event_df["Events"].dropna().unique())
all_types = sorted(event_df["Type (from Event) 2"].dropna().unique())

selected_events = st.sidebar.multiselect("Select Events", all_events)
selected_types = st.sidebar.multiselect("Select Event Types", all_types)

# Apply filters
if selected_events:
    event_df = event_df[event_df["Events"].isin(selected_events)]
elif selected_types:
    event_df = event_df[event_df["Type (from Event) 2"].isin(selected_types)]

# ============== RAW FEEDBACK ==============
if not event_df.empty:
    st.subheader("📝 Raw Feedback")

    if selected_types and not selected_events:
        # Group by event type
        for etype in event_df["Type (from Event) 2"].dropna().unique():
            st.write(f"### {etype}")
            st.dataframe(
                event_df[event_df["Type (from Event) 2"] == etype][
                    ["Events"] + list(text_summary_questions.keys())
                ],
                use_container_width=True
            )
    else:
        # Group by event
        for event in event_df["Events"].dropna().unique():
            st.write(f"### {event}")
            st.dataframe(
                event_df[event_df["Events"] == event][
                    ["Events"] + list(text_summary_questions.keys())
                ],
                use_container_width=True
            )

# ============== SUMMARIES ==============
if not event_df.empty:
    filter_summary = []
    if selected_events:
        filter_summary.append(f"Events: {', '.join(selected_events)}")
    if selected_types:
        filter_summary.append(f"Types: {', '.join(selected_types)}")

    st.subheader("📌 Summary for: " + (" | ".join(filter_summary) if filter_summary else "All Data"))

    results = []

    if selected_types and not selected_events:
        # 🔹 Summarize by Event Type
        for etype in event_df["Type (from Event) 2"].dropna().unique():
            type_data = event_df[event_df["Type (from Event) 2"] == etype]

            # Numeric
            for col in numeric_questions.keys():
                if col in type_data.columns:
                    numeric_series = type_data[col].dropna().apply(extract_leading_number)
                    avg_val = round(numeric_series.mean(), 2) if not numeric_series.empty else ""
                    results.append({"Event Type": etype, "Question": col + "_Average", "Value": avg_val})

            # Summaries
            for col in text_summary_questions.keys():
                if col in type_data.columns:
                    all_text = " ".join(type_data[col].dropna().astype(str))
                    summary = summarize_text_one_sentence(all_text)
                    results.append({"Event Type": etype, "Question": col + "_Summary", "Value": summary})

            # Themes
            for col in text_theme_questions.keys():
                if col in type_data.columns:
                    all_text = " ".join(type_data[col].dropna().astype(str))
                    themes = extract_themes_with_counts(all_text)
                    results.append({"Event Type": etype, "Question": col + "_Themes", "Value": themes})

        results_df = pd.DataFrame(results)[["Event Type", "Question", "Value"]]

        st.write("### 📊 Student Feedback Summary (by Event Type)")
        st.data_editor(
            results_df,
            use_container_width=True,
            column_config={
                "Event Type": st.column_config.TextColumn("Event Type", width=120),
                "Question": st.column_config.TextColumn("Question", width=120),
                "Value": st.column_config.TextColumn("Value", width=750),
            },
            hide_index=True,
            disabled=True
        )

    else:
        # 🔹 Summarize by Event
        for event in event_df["Events"].dropna().unique():
            event_data = event_df[event_df["Events"] == event]

            # Numeric
            for col in numeric_questions.keys():
                if col in event_data.columns:
                    numeric_series = event_data[col].dropna().apply(extract_leading_number)
                    avg_val = round(numeric_series.mean(), 2) if not numeric_series.empty else ""
                    results.append({"Event": event, "Question": col + "_Average", "Value": avg_val})

            # Summaries
            for col in text_summary_questions.keys():
                if col in event_data.columns:
                    all_text = " ".join(event_data[col].dropna().astype(str))
                    summary = summarize_text_one_sentence(all_text)
                    results.append({"Event": event, "Question": col + "_Summary", "Value": summary})

            # Themes
            for col in text_theme_questions.keys():
                if col in event_data.columns:
                    all_text = " ".join(event_data[col].dropna().astype(str))
                    themes = extract_themes_with_counts(all_text)
                    results.append({"Event": event, "Question": col + "_Themes", "Value": themes})

        results_df = pd.DataFrame(results)[["Event", "Question", "Value"]]

        st.write("### 📊 Student Feedback Summary (by Event)")
        st.data_editor(
            results_df,
            use_container_width=True,
            column_config={
                "Event": st.column_config.TextColumn("Event", width=120),
                "Question": st.column_config.TextColumn("Question", width=120),
                "Value": st.column_config.TextColumn("Value", width=750),
            },
            hide_index=True,
            disabled=True
        )
