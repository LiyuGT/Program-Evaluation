# Multi-select for event selection with "All Events" option
event_names = sorted(table_df["Events"].dropna().unique())
event_options = ["All Events"] + event_names
selected_events = st.multiselect("Select Event(s)", event_options, default="All Events")

# If "All Events" is selected, use all events
if "All Events" in selected_events:
    filtered_events = event_names
else:
    filtered_events = selected_events

# Filter data for selected events
event_df = table_df[table_df["Events"].isin(filtered_events)]

if not event_df.empty:
    st.subheader(f"📌 Summary for: {', '.join(filtered_events)}")

    # ========== Build results (long format) ==========
    results = []

    for event in filtered_events:
        event_data = event_df[event_df["Events"] == event]

        # Numeric
        for col, new_col in numeric_questions.items():
            if col in event_data.columns:
                numeric_series = event_data[col].dropna().apply(extract_leading_number)
                avg_val = round(numeric_series.mean(), 2) if not numeric_series.empty else ""
                results.append({
                    "Event": event,
                    "Question": col + "_Average",
                    "Value": avg_val
                })

        # Summaries
        for col, new_col in text_summary_questions.items():
            if col in event_data.columns:
                all_text = " ".join(event_data[col].dropna().astype(str))
                summary = summarize_text_one_sentence(all_text)
                results.append({
                    "Event": event,
                    "Question": col + "_Summary",
                    "Value": summary
                })

        # Themes
        for col, new_col in text_theme_questions.items():
            if col in event_data.columns:
                all_text = " ".join(event_data[col].dropna().astype(str))
                themes = extract_themes_with_counts(all_text)
                results.append({
                    "Event": event,
                    "Question": col + "_Themes",
                    "Value": themes
                })

    # Convert to DataFrame (long format)
    results_df = pd.DataFrame(results)

    # Show results
    st.write("### 📊 Student Feedback Summary")
    st.dataframe(results_df, use_container_width=True)

    # ========== Raw Feedback Section ==========
    st.write("### 📝 Raw Student Feedback")
    feedback_cols = [c for c in event_df.columns if c.startswith("Question")]
    st.dataframe(event_df[["Events"] + feedback_cols], use_container_width=True)

else:
    st.warning("No data found for the selected event(s).")
