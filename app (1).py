import streamlit as st
import io
import base64
import pandas as pd
import plotly.express as px
from src.parsing.parser import extract_text_from_resume
from src.llm.reviewer import get_resume_feedback
from src.helpers.highlight import highlight_resume_pdf
from pydantic import ValidationError

st.set_page_config(layout="wide", page_title="AI Resume Reviewer", page_icon="📄")

# --- Custom CSS for a professional and modern look ---
st.markdown(
    """
    <style>
    .reportview-container {
        background: #F8F9FA; /* Off-white background */
    }
    .main .block-container {
        padding-top: 2rem;
        padding-right: 2rem;
        padding-left: 2rem;
        padding-bottom: 2rem;
    }
    .st-eb {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transition: transform 0.2s;
    }
    .st-eb:hover {
        transform: translateY(-5px);
    }
    h1 {
        color: #1A3E60;
        font-weight: 900;
        letter-spacing: -1px;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    h2 {
        color: #2D5B8D;
        font-weight: 700;
        border-left: 5px solid #2D5B8D;
        padding-left: 10px;
    }
    h3 {
        color: #3C72B0;
        font-weight: 600;
    }
    .stButton>button {
        background-color: #2D5B8D;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 12px 24px;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        transition: background-color 0.3s, transform 0.2s;
    }
    .stButton>button:hover {
        background-color: #1A3E60;
        transform: translateY(-2px);
    }
    
    /* FIX FOR METRIC FONT COLOR */
    .stMetric {
        background-color: #EBF5FF;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        border: 1px solid #C1DDF7;
    }
    .stMetric > div > div:first-child {
        color: #1A3E60; /* Color for the metric label */
        font-weight: bold;
    }
    .stMetric > div > div:last-child {
        color: #1A3E60; /* Color for the metric value */
        font-weight: bold;
        font-size: 2.5rem; 
    }
    .stMetric > div > div:nth-child(2) {
        color: #1A3E60; /* Fallback for delta label */
    }
    /* END FIX */

    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #EBF5FF;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: bold;
        color: #3C72B0;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #3C72B0;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Main App Title and Description ---
st.title("📄 **AI Resume Reviewer**")
st.markdown("### **Get a professional, data-driven analysis of your resume in seconds.**")
st.markdown("---")

# --- Input Section ---
with st.expander("🚀 **1. Upload & Analyze Your Resume**", expanded=True):
    col_file, col_role = st.columns([1, 1.5])
    with col_file:
        resume = st.file_uploader("**Upload your resume**", "pdf")
    with col_role:
        job_role = st.text_area("**Target Job Role**", placeholder="e.g., Senior Data Scientist")
        job_description = st.text_area("**Job Description (optional)**", placeholder="Paste the job description here for a more tailored analysis.")

    st.markdown("---") # Add a separator
    if st.button("✨ **Analyze My Resume**"):
        if not resume or not job_role:
            st.warning("⚠️ **Please upload your resume and enter a target job role to begin.**")
        else:
            with st.spinner("⏳ **Generating professional AI feedback...** This may take a moment."):
                try:
                    resume_text = extract_text_from_resume(resume)
                    resume.seek(0)
                    feedback = get_resume_feedback(resume_text, job_role, job_description)

                    st.success("✅ **Analysis Complete!**")
                    st.balloons()
                    st.markdown("---")
                    
                    # --- Results Section - Tabs ---
                    tab1, tab2 = st.tabs(["📊 **Overview & Metrics**", "📄 **Highlighted Resume**"])

                    with tab1:
                        st.header("Results & Key Insights")
                        st.markdown("---")

                        # Score and Summary Section
                        col_score, col_summary = st.columns([1, 2])
                        with col_score:
                            st.metric(label="**Overall Match Score**", value=f"**{feedback.score}/100**")
                            score_bar_color = "green" if feedback.score >= 80 else "orange" if feedback.score >= 60 else "red"
                            st.progress(feedback.score / 100, text=f"Match: {feedback.score}%")
                            
                            st.markdown("---")

                            st.subheader("Key Metrics")
                            metrics_data = {
                                "Category": ["Experience", "Skills", "Keywords"],
                                "Score": [40, 35, 25]  # Placeholder weights for the pie chart
                            }
                            metrics_df = pd.DataFrame(metrics_data)
                            fig_pie = px.pie(metrics_df, values="Score", names="Category", title="**Score Breakdown**",
                                             color_discrete_sequence=px.colors.qualitative.Pastel, hole=0.4)
                            fig_pie.update_traces(textinfo='percent+label')
                            st.plotly_chart(fig_pie, use_container_width=True)

                        with col_summary:
                            st.subheader("Resume Summary")
                            st.info(f"✨ **{feedback.summary}**")
                            
                            st.subheader("Strengths & Weaknesses")
                            data = {
                                "Category": ["Strengths", "Weaknesses", "Missing Skills"],
                                "Count": [len(feedback.strengths), len(feedback.weaknesses), len(feedback.missing_skills)]
                            }
                            df = pd.DataFrame(data)
                            fig_bar = px.bar(df, x="Category", y="Count",
                                             title="**Analysis at a Glance**",
                                             labels={"Count": "Number of Points"},
                                             color="Category",
                                             color_discrete_map={"Strengths": "#28A745", "Weaknesses": "#DC3545", "Missing Skills": "#FFC107"},
                                             text="Count")
                            fig_bar.update_layout(showlegend=False)
                            st.plotly_chart(fig_bar, use_container_width=True)
                        
                        st.markdown("---")
                        
                        st.subheader("Detailed Feedback")
                        col_strength, col_weakness, col_improvement = st.columns(3)

                        with col_strength:
                            st.markdown("#### ✅ **Strengths**")
                            if feedback.strengths:
                                for s in feedback.strengths:
                                    st.success(f"- **{s}**")
                            else:
                                st.info("No specific strengths highlighted, but the resume is solid.")

                        with col_weakness:
                            st.markdown("#### ❌ **Weaknesses**")
                            if feedback.weaknesses:
                                for weak in feedback.weaknesses:
                                    st.error(f"- **{weak}**")
                            else:
                                st.info("No major weaknesses detected. Great job!")

                        with col_improvement:
                            st.markdown("#### 💡 **Improvements**")
                            if feedback.improvements:
                                for imp in feedback.improvements:
                                    st.warning(f"- **{imp}**")
                            else:
                                st.info("Your resume is well-optimized. Fantastic!")

                    with tab2:
                        st.header("Highlighted Resume Preview")
                        st.markdown("This view shows your resume with key areas for improvement highlighted. Red for weaknesses and yellow for suggested improvements.")
                        
                        pdf_bytes = io.BytesIO(resume.read())
                        highlighted_pdf = highlight_resume_pdf(pdf_bytes, feedback.improvements, feedback.weaknesses)

                        b64_pdf = base64.b64encode(highlighted_pdf.getvalue()).decode("utf-8")
                        pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
                        st.components.v1.html(pdf_display, height=800, scrolling=True)

                        st.download_button(
                            label="📥 **Download Highlighted Resume**",
                            data=highlighted_pdf.getvalue(),
                            file_name="highlighted_resume.pdf",
                            mime="application/pdf",
                        )

                except (ValidationError, ValueError) as e:
                    st.error(f"❌ **An error occurred during analysis:** {e}")
                except Exception as e:
                    st.error(f"❌ **An unexpected error occurred:** {e}")