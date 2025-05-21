import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
import uuid
from recommender import recommend_jobs
from unsupervised_recommender import recommend_unsupervised

# Full CSV file path for interaction logs
# need to set up google api - usign google console to store interaction data on google sheets
INTERACTION_LOG = "/tmp/user_interactions.csv"

# Load jobs data
jobs_df = pd.read_csv("jobs.csv")

# Extract unique job types (skills) from 'Job type' column
available_skills = sorted(jobs_df["Job type"].dropna().unique().tolist())

# List of all Indian states
indian_states = [
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh',
    'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland',
    'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura', 'Uttarakhand', 'Uttar Pradesh', 'West Bengal',
    'Andaman and Nicobar Islands', 'Chandigarh', 'Dadra and Nagar Haveli and Daman and Diu', 'Lakshadweep', 'Delhi', 'Puducherry'
]

# Initialize session state variables
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'page' not in st.session_state:
    st.session_state.page = 'login'
if 'login_trigger' not in st.session_state:
    st.session_state.login_trigger = 0
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}
if 'recommendations' not in st.session_state:
    st.session_state.recommendations = None
if 'interaction_trigger' not in st.session_state:
    st.session_state.interaction_trigger = 0
if 'generated_otp' not in st.session_state:
    st.session_state.generated_otp = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = 'user'  # default role

# -------------- LOGIN PAGE --------------
if st.session_state.page == 'login':
    st.title("🔐 Login")

    tab1, tab2 = st.tabs(["User Login", "Admin Login"])

    with tab1:
        phone_number = st.text_input("Enter your phone number")

        # Validate phone number length and digits
        if phone_number and (not phone_number.isdigit() or len(phone_number) != 10):
            st.error("Please enter a valid 10-digit phone number.")

        valid_phone = phone_number.isdigit() and len(phone_number) == 10
        send_otp_button = st.button("Send OTP", disabled=not valid_phone)

        if send_otp_button:
            st.session_state.generated_otp = "123456"
            st.success("OTP sent! Use 123456 for demo.")

        if st.session_state.generated_otp:
            entered_otp = st.text_input("Enter OTP", key="entered_otp")
            if st.button("Verify OTP"):
                if entered_otp == st.session_state.generated_otp:
                    st.session_state.authenticated = True
                    st.session_state.user_role = "user"
                    st.session_state.page = 'main'  # Switch to main app page
                    st.session_state.login_trigger += 1
                    st.experimental_rerun()
                else:
                    st.error("Incorrect OTP")

    with tab2:
        st.subheader("Admin Access")
        admin_email = st.text_input("Enter your work email", key="admin_email_input")
        if st.button("Admin Access"):
            if admin_email.lower().endswith("@innodatatics.com"):
                st.session_state.authenticated = True
                st.session_state.user_role = "admin"
                st.session_state.page = "admin_view"  # Redirect to admin view page
                st.success("Admin access granted.")
                st.experimental_rerun()
            else:
                st.error("Access denied. Please use a valid innodatatics.com email.")

st.markdown("---")

# -------------- MAIN APP PAGE --------------
elif st.session_state.page == 'main' and st.session_state.authenticated:
    st.title("🧠 AI Job Recommender")

    # Logout button
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.page = 'login'
        st.session_state.generated_otp = None
        st.session_state.recommendations = None
        st.session_state.user_data = {}
        st.rerun()

    # User input form
    with st.form("user_input_form"):
        name = st.text_input("Name")
        age = st.number_input("Age", min_value=18, max_value=70, value=25)
        location = st.selectbox("Select Your Location (State)", indian_states)
        skills = st.multiselect("Select Skills (Job Types)", available_skills)
        salary = st.number_input("Expected Monthly Salary (INR)", min_value=0)
        model_choice = st.selectbox("Choose Recommendation Model", ["Rule-Based", "Unsupervised"])
        top_n = st.slider("Number of Job Recommendations", 1, 20, 3)
        submitted = st.form_submit_button("Get Recommendations")

    # Handle recommendation generation with basic validation
    if submitted:
        if not name.strip():
            st.error("Please enter your name.")
        elif not skills or len(skills) == 0:
            st.error("Please select at least one skill.")
        else:
            with st.spinner('Generating recommendations...'):
                session_id = str(uuid.uuid4())
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                skills_str = ", ".join(skills) if isinstance(skills, list) else skills
                st.session_state.user_data = {
                    "name": name,
                    "age": age,
                    "location": location,
                    "skills": skills_str,
                    "salary": salary,
                    "top_n": top_n,
                    "session_id": session_id,
                    "timestamp": timestamp
                }

                if model_choice == "Rule-Based":
                    st.session_state.recommendations = recommend_jobs(
                        user_name=name,
                        user_age=age,
                        user_location=location,
                        user_skills=skills_str,
                        expected_salary=salary,
                        top_n=top_n
                    )
                else:
                    st.session_state.recommendations = recommend_unsupervised(
                        skills=skills_str,  # Convert list to comma-separated string
                        location=location,
                        expected_monthly_salary=salary,
                        top_n=top_n
                    )
                
                
    # Display recommendations if available
    if st.session_state.recommendations is not None and not st.session_state.recommendations.empty:
        st.write(f"🔍 Recommendations for **{st.session_state.user_data['name']}**:")
        recommendations_display = st.session_state.recommendations[['Company', 'Job type', 'State', 'match_score']].sort_values(by="match_score", ascending=False)

        for index, row in recommendations_display.iterrows():
            job_key = f"expander_{index}"
            is_open = st.session_state.get("last_clicked_job") == job_key
        
            with st.expander(f"📌 {row['Company']}", expanded=is_open):
                st.write(f"**Job Type**: {row['Job type']}")
                st.write(f"**Location**: {row['State']}")
                st.write(f"**Match Score**: {row['match_score']}")
        
                if st.button(f"I'm interested in {row['Company']}", key=f"button_{job_key}"):
                    st.session_state["last_clicked_job"] = job_key
                    st.session_state["clicked_job"] = job_key  #
        
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
                    st.session_state['interaction_trigger'] = st.session_state.get('interaction_trigger', 0) + 1
                    st.rerun()  # 🔄 Trigger page refresh after saving
        
                # After rerun, show success if this was the clicked job
                if st.session_state.get('clicked_job') == job_key:
                    st.success(f"Your interest in {row['Company']} has been logged!")
        
    elif st.session_state.recommendations is not None and st.session_state.recommendations.empty:
        st.warning("⚠️ No jobs found matching your profile.")

# ----------- ADMIN VIEW PAGE -----------
elif st.session_state.page == "admin_view" and st.session_state.authenticated and st.session_state.user_role == "admin":
    st.title("🛠 Admin View")

    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.page = 'login'
        st.session_state.user_role = 'user'
        st.experimental_rerun()

    selected_action = st.radio("Choose an action:", [
        "View Dashboard",
        "Download Interaction Data",
        "Append to jobs.csv"
    ])

    if selected_action == "View Dashboard":
        st.info("📊 Show some Streamlit charts or tables here.")

    elif selected_action == "Download Interaction Data":
        if os.path.exists(INTERACTION_LOG):
            interaction_df = pd.read_csv(INTERACTION_LOG)
            csv = interaction_df.to_csv(index=False).encode("utf-8")
            st.download_button("Download Interaction CSV", csv, "interactions.csv", "text/csv")
        else:
            st.warning("No interaction data found.")

    elif selected_action == "Append to jobs.csv":
        st.info("📥 Add your job appending logic here.")
        new_job = st.text_area("Paste new job data (CSV format)")
        if st.button("Append Job"):
            if new_job:
                try:
                    from io import StringIO
                    new_df = pd.read_csv(StringIO(new_job))
                    existing_df = pd.read_csv("jobs.csv")
                    combined = pd.concat([existing_df, new_df], ignore_index=True)
                    combined.to_csv("jobs.csv", index=False)
                    st.success("New job(s) added successfully.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Please enter job data first.")
