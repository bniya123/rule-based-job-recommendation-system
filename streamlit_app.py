import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
import uuid
from recommender import recommend_jobs

# Load jobs data and extract skills
JOBS_DATA_PATH = "jobs.csv"  # Update with the correct path
jobs_df = pd.read_csv(JOBS_DATA_PATH)

# Extract unique skills from jobs data
def extract_unique_skills(jobs_df, skill_column="Job type"):
    if skill_column not in jobs_df.columns:
        st.warning(f"⚠️ Column '{skill_column}' not found. Available columns: {jobs_df.columns.tolist()}")
        return []
    all_skills = []
    for skill_list in jobs_df[skill_column].dropna():
        all_skills.extend([skill.strip() for skill in skill_list.split(',')])
    return sorted(set(all_skills))

available_skills = extract_unique_skills(jobs_df, skill_column="Job type")

# Full CSV file path for interaction logs
INTERACTION_LOG = "C:/Users/fatim/ISB/Terms Resources/Capstone Project/job-recommender-streamlit/user_interactions.csv"

# Ensure the directory for CSV exists
os.makedirs(os.path.dirname(INTERACTION_LOG), exist_ok=True)

# List of all Indian states
indian_states = [
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh',
    'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland',
    'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura', 'Uttarakhand', 'Uttar Pradesh', 'West Bengal',
    'Andaman and Nicobar Islands', 'Chandigarh', 'Dadra and Nagar Haveli and Daman and Diu', 'Lakshadweep', 'Delhi', 'Puducherry'
]

# Session state to store recommendations
if 'recommendations' not in st.session_state:
    st.session_state.recommendations = None
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}

# App UI
st.title("🧠 AI Job Recommender")

# User input form
with st.form("user_input_form"):
    name = st.text_input("Name")
    age = st.number_input("Age", min_value=18, max_value=70, value=25)
    location = st.selectbox("Select Your Location (State)", indian_states)
    skills_selected = st.multiselect("Select Your Skills", options=available_skills)
    salary = st.number_input("Expected Monthly Salary (INR)", min_value=0)
    top_n = st.slider("Number of Job Recommendations", 1, 10, 3)
    submitted = st.form_submit_button("Get Recommendations")

# Handle recommendation generation
if submitted:
    session_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.user_data = {
        "name": name,
        "age": age,
        "location": location,
        "skills": ", ".join(skills_selected),
        "salary": salary,
        "top_n": top_n,
        "session_id": session_id,
        "timestamp": timestamp
    }

    st.session_state.recommendations = recommend_jobs(
        user_name=name,
        user_age=age,
        user_location=location,
        user_skills=", ".join(skills_selected),
        expected_salary=salary,
        top_n=top_n
    )

# Display recommendations if available
if st.session_state.recommendations is not None and not st.session_state.recommendations.empty:
    st.write(f"🔍 Recommendations for **{st.session_state.user_data['name']}**:")
    recommendations_display = st.session_state.recommendations[['Company', 'Job type', 'State', 'match_score']]

    for index, row in recommendations_display.iterrows():
        with st.expander(f"📌 {row['Company']}"):
            st.write(f"**Job Type**: {row['Job type']}")
            st.write(f"**Location**: {row['State']}")
            st.write(f"**Match Score**: {row['match_score']}")
            
            if st.button(f"I'm interested in {row['Company']}", key=f"button_{row['Company']}_{index}"):
                # Log interaction
                interaction_data = {
                    "Timestamp": st.session_state.user_data['timestamp'],
                    "Session ID": st.session_state.user_data['session_id'],
                    "Name": st.session_state.user_data['name'],
                    "Age": st.session_state.user_data['age'],
                    "Location": st.session_state.user_data['location'],
                    "Skills": st.session_state.user_data['skills'],
                    "Expected Salary": st.session_state.user_data['salary'],
                    "Top N": st.session_state.user_data['top_n'],
                    "Jobs Recommended": "|".join(st.session_state.recommendations["Company"].astype(str).tolist()),
                    "Jobs Clicked": row['Company'],
                    "Match Scores": "|".join(st.session_state.recommendations["match_score"].astype(str).tolist()),
                }

                # Save to CSV
                if os.path.exists(INTERACTION_LOG):
                    df_log = pd.read_csv(INTERACTION_LOG)
                    df_log = pd.concat([df_log, pd.DataFrame([interaction_data])], ignore_index=True)
                else:
                    df_log = pd.DataFrame([interaction_data])

                df_log.to_csv(INTERACTION_LOG, index=False)
                st.success(f"Your interest in {row['Company']} has been logged!")
                time.sleep(5)
                st.session_state["rerun_trigger"] = st.session_state.get("rerun_trigger", 0) + 1
                st.query_params.update({"trigger": st.session_state["rerun_trigger"]})


elif st.session_state.recommendations is not None:
    st.warning("No jobs found matching your profile.")
