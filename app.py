# app2.py
import io
import base64
import streamlit as st
import pandas as pd
import plotly.express as px
from pydantic import ValidationError
from src.parsing.parser import extract_text_from_resume
from src.llm.reviewer import get_resume_feedback
from src.helpers.highlight import highlight_resume_pdf_keywords
from src.helpers.lang import get_resume_language

import subprocess
import json
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

st.set_page_config(layout="wide", page_title="AI Resume Reviewer", page_icon="📄")

# --- Custom CSS ---
st.markdown(
    """
    <style>
    .reportview-container { background: #F8F9FA; }
    .main .block-container { padding: 2rem; }
    .st-eb { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); transition: transform 0.2s; }
    .st-eb:hover { transform: translateY(-5px); }
    h1 { color: #1A3E60; font-weight: 900; letter-spacing: -1px; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); }
    h2 { color: #2D5B8D; font-weight: 700; border-left: 5px solid #2D5B8D; padding-left: 10px; }
    h3 { color: #3C72B0; font-weight: 600; }
    .stButton>button { background-color: #2D5B8D; color: white; font-weight: bold; border-radius: 8px; padding: 12px 24px; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.2); transition: background-color 0.3s, transform 0.2s; }
    .stButton>button:hover { background-color: #1A3E60; transform: translateY(-2px); }
    .stMetric { background-color: #EBF5FF; border-radius: 10px; padding: 20px; text-align: center; border: 1px solid #C1DDF7; }
    .stMetric > div > div:first-child { color: #1A3E60; font-weight: bold; }
    .stMetric > div > div:last-child { color: #1A3E60; font-weight: bold; font-size: 2.5rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { background-color: #EBF5FF; border-radius: 8px 8px 0 0; padding: 10px 20px; font-weight: bold; color: #3C72B0; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background-color: #3C72B0; color: white; }
    .highlight-strength { background-color: #90EE90; padding: 4px 8px; border-radius: 4px; color: #000000; margin: 2px; display: inline-block; border: 1px solid #4CAF50; }
    .highlight-weakness { background-color: #FFB6C1; padding: 4px 8px; border-radius: 4px; color: #000000; margin: 2px; display: inline-block; border: 1px solid #FF5252; }
    .highlight-container { background-color: #2B2B2B; color: #F8F8F8; padding: 20px; border-radius: 10px; border: 1px solid #444; max-height: 600px; overflow-y: auto; font-family: 'Courier New', monospace; font-size: 14px; line-height: 1.6; }
    .context-box { background-color: #1E1E1E; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid; }
    .context-strength { border-left-color: #4CAF50; }
    .context-weakness { border-left-color: #FF5252; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state
if 'feedback' not in st.session_state:
    st.session_state.feedback = None
if 'resume_uploaded' not in st.session_state:
    st.session_state.resume_uploaded = False
if 'resume_text' not in st.session_state:
    st.session_state.resume_text = ""
if 'resume_file' not in st.session_state:
    st.session_state.resume_file = None

def call_local_mistral(prompt: str, model: str = "mistral") -> str:
    """Call local Mistral/Ollama model and return raw text."""
    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt.encode("utf-8"),
        capture_output=True
    )
    return result.stdout.decode("utf-8")

def request_improved_resume(resume_text: str, job_role: str, improvements: list[str]) -> dict:
    """Ask LLM to rewrite resume with improvements applied."""

    # Detect language
    resume_language = get_resume_language(resume_text)
    language_instruction = (
        f"**IMPORTANT:** All json fields MUST BE in {resume_language} language. "
        "Both the improved_resume AND changes_log. Do not respond without ensuring this fact."
    )

    # Build the prompt directly as a formatted string
    prompt = f"""
You are a professional resume editor.
Take the following resume and improve it by:
- Fixing weaknesses
- Applying the listed improvements
- Keeping all factual information intact
- Making language stronger and more professional

Job Role: {job_role}
Resume Text:
{resume_text}

{language_instruction}

Return JSON in this format:
{{
  "improved_resume": "Improved resume text here",
  "changes_log": ["list of changes made"]
}}
IMPORTANT: Respond with valid JSON ONLY. Do NOT include any text outside the JSON object. Escape quotes in resume text properly.
RESPOND WITH JSON ONLY
DO NOT ADD ANY EXTRA TEXT
JSON ONLY
ONLY JSON FORMAT
"""

    if improvements:
        prompt += "\n\nImprovements to apply:\n- " + "\n- ".join(improvements)

    # Call the LLM
    raw_output = call_local_mistral(prompt)

    # Parse JSON
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError:
        json_part = raw_output[raw_output.find("{"): raw_output.rfind("}") + 1]
        data = json.loads(json_part)

    return data

def request_resume_comparison(resume_text: str, job_role: str, job_desc: str = "") -> dict:
    """
    Compare a resume against a job role or description.
    Ensures output is in the same language as the resume.
    If job_desc is empty, defaults to general expectations.
    """
    # Detect resume language (using your existing function)
    resume_language = get_resume_language(resume_text)

    if not job_desc.strip():
        job_desc = f"Job description not provided. Analysis is based on general expectations for the role: {job_role}."

    COMPARE_PROMPT_TEMPLATE = f"""
    You are a professional resume reviewer. Keep the output in the same language as the resume: {resume_language}.
    
    Compare the following resume with the job role and/or description:

    Job Role: {job_role}
    Job Description: {job_desc}

    Resume Text:
    {resume_text}

    Provide a JSON output with keys:
    {{
        "matched_skills": ["skills that match or are relevant"],
        "missing_skills": ["skills expected but missing"],
        "recommendations": ["general improvements or tailoring suggestions"]
    }}

    IMPORTANT: Your entire response must be valid JSON only. Do not add any explanatory text.
    """

    raw_output = call_local_mistral(COMPARE_PROMPT_TEMPLATE)

    # Robust JSON parsing
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError:
        json_part = raw_output[raw_output.find("{"): raw_output.rfind("}") + 1]
        data = json.loads(json_part)

    return data

def display_resume_highlights(strengths, weaknesses):
    """Display exact highlighted points from resume in Streamlit."""
    html_output = "<div style='padding: 10px; max-height: 500px; overflow-y: auto; background-color: #1E1E1E; color: #F8F8F8; border-radius: 10px;'>"

    if strengths:
        html_output += "<h4 style='color: #90EE90;'>✅ Strengths:</h4>"
        for s in strengths:
            html_output += f"<div style='background-color:#90EE90; color:#000; padding:4px 8px; border-radius:4px; margin:4px 0;'>{s}</div>"

    if weaknesses:
        html_output += "<h4 style='color: #FFB6C1;'>❌ Areas for Improvement:</h4>"
        for w in weaknesses:
            html_output += f"<div style='background-color:#FFB6C1; color:#000; padding:4px 8px; border-radius:4px; margin:4px 0;'>{w}</div>"

    if not strengths and not weaknesses:
        html_output += "<p>No specific highlights found in your resume.</p>"

    html_output += "</div>"

    st.components.v1.html(html_output, height=300, scrolling=True)

def render_markdown_to_pdf_bytes(text: str) -> io.BytesIO:
    """Render improved resume text into a PDF."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 50
    for line in text.split("\n"):
        c.drawString(50, y, line.strip())
        y -= 15
        if y < 50:
            c.showPage()
            y = height - 50
    c.save()

    buffer.seek(0)
    return buffer

st.title("📄 AI Resume Reviewer")
st.markdown("### Get a professional, data-driven analysis of your resume in seconds.")
st.markdown("---")

with st.expander("🚀 Upload & Analyze Your Resume", expanded=True):
    col_file, col_role = st.columns([1, 1.5])

    with col_file:
        input_method = st.radio(
            "Choose input method:",
            ["Upload PDF", "Paste Text"],
            index=0,
            key="input_method"
        )

        if input_method == "Upload PDF":
            resume = st.file_uploader("Upload your resume (PDF)", type="pdf", key="resume_uploader")
            if resume:
                st.session_state.resume_uploaded = True
                st.session_state.resume_file = resume
                st.session_state.resume_file_bytes = None  # don’t read yet
                st.session_state.resume_text = None  # clear text mode
        else:
            resume_text = st.text_area(
                "Paste your resume text",
                placeholder="Paste the full text of your resume here...",
                key="resume_textbox",
                height=300
            )
            if resume_text.strip():
                st.session_state.resume_uploaded = True
                st.session_state.resume_text = resume_text
                st.session_state.resume_file_bytes = None
                st.session_state.resume_file = None

    with col_role:
        job_role = st.text_input(
            "Target Job Role",
            placeholder="e.g., Senior Data Scientist",
            key="job_role_input"
        )
        job_description = st.text_area(
            "Job Description (optional)",
            placeholder="Paste the job description here for a more tailored analysis.",
            key="job_desc_input"
        )

    if st.session_state.get("resume_file") and not st.session_state.get("resume_file_bytes"):
        st.session_state.resume_file_bytes = st.session_state.resume_file.read()

    st.markdown("---")

    if st.button("✨ Analyze My Resume", key="analyze_btn"):
        
        if not st.session_state.resume_uploaded:
            st.warning("Please upload your resume before analyzing.")
        elif not job_role or job_role.strip() == "":
            st.warning("Please enter a target job role (this is required).")
        else:
            try:
                with st.spinner("⏳ Generating AI feedback..."):
                    if st.session_state.get("resume_file"):
                        resume_text = extract_text_from_resume(resume)
                        st.session_state.resume_text = resume_text
                    
                    try:
                        resume.seek(0)
                    except Exception:
                        pass

                    feedback = get_resume_feedback(resume_text, job_role, job_description)
                    
                    # Store feedback in session state
                    st.session_state.feedback = feedback
                    st.session_state.job_role = job_role
                    
                    # Force re-render
                    st.rerun()

            except (ValidationError, ValueError) as e:
                st.error(f"Analysis error: {e}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

# Display results if feedback exists
if st.session_state.feedback:
    feedback = st.session_state.feedback
    job_role = getattr(st.session_state, 'job_role', 'the target role')
    
    st.success("✅ Analysis complete!")
    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview & Metrics", "📄 Improved Resume", "🖋️Resume Highlights", "⚖️Resume Comparison"])

    with tab1:
        st.header(f"Results & Key Insights for {job_role}")
        col_score, col_summary = st.columns([1, 2])
        
        with col_score:
            st.metric(label="Overall Match Score", value=f"{feedback.score}/100")
            st.progress(feedback.score / 100.0)
            
            # Additional metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Strengths", len(feedback.strengths))
            with col2:
                st.metric("Areas to Improve", len(feedback.weaknesses))
            with col3:
                st.metric("Missing Skills", len(feedback.missing_skills))

        with col_summary:
            st.subheader("Resume Summary")
            st.info(feedback.summary)

            st.subheader("Analysis Overview")
            # Dynamic data based on actual feedback
            data = {
                "Category": ["Strengths", "Weaknesses", "Missing Skills", "Improvements"],
                "Count": [
                    len(feedback.strengths), 
                    len(feedback.weaknesses), 
                    len(feedback.missing_skills),
                    len(feedback.improvements)
                ],
            }
            df = pd.DataFrame(data)
            fig_bar = px.bar(df, x="Category", y="Count", title="Analysis Breakdown", text="Count")
            fig_bar.update_traces(marker_color=['#2CA02C', '#D62728', '#FF7F0E', '#1F77B4'])
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("Detailed Feedback")
        col_s, col_w, col_m, col_i = st.columns(4)
        
        with col_s:
            st.markdown("#### ✅ Strengths")
            if feedback.strengths:
                for s in feedback.strengths:
                    st.success(f"• {s}")
            else:
                st.info("No strengths identified")
        
        with col_w:
            st.markdown("#### ❌ Weaknesses")
            if feedback.weaknesses:
                for w in feedback.weaknesses:
                    st.error(f"• {w}")
            else:
                st.info("No weaknesses identified")
        
        with col_m:
            st.markdown("#### 🔍 Missing Skills")
            if feedback.missing_skills:
                for skill in feedback.missing_skills:
                    st.warning(f"• {skill}")
            else:
                st.info("No missing skills identified")
        
        with col_i:
            st.markdown("#### 💡 Improvements")
            if feedback.improvements:
                for imp in feedback.improvements:
                    st.info(f"• {imp}")
            else:
                st.info("No improvements suggested")

    with tab2:
        st.header("Improved Resume (PDF)")

        try:
            resume_text = None

            # Case 1: user pasted text
            if st.session_state.get("resume_text"):
                resume_text = st.session_state.resume_text

            # Case 2: user uploaded PDF
            elif st.session_state.get("resume_file"):
                # Read bytes only when needed
                if not st.session_state.get("resume_file_bytes"):
                    st.session_state.resume_file_bytes = st.session_state.resume_file.read()
                resume_text = extract_text_from_resume(io.BytesIO(st.session_state.resume_file_bytes))

            if resume_text:
                with st.spinner("✨ Improving your resume..."):
                    result = request_improved_resume(
                        resume_text,
                        job_role,
                        feedback.improvements or []
                    )
                    improved_text = result.get("improved_resume", "")
                    changes_log = result.get("changes_log", [])

                    # Generate improved PDF
                    pdf_stream = render_markdown_to_pdf_bytes(improved_text)

                    # Show changes log
                    if changes_log:
                        st.subheader("✅ Changes Made")
                        for change in changes_log:
                            st.markdown(f"- {change}")

                    # Show PDF inline
                    b64 = base64.b64encode(pdf_stream.getvalue()).decode("utf-8")
                    iframe = f'<iframe src="data:application/pdf;base64,{b64}" width="700" height="1000"></iframe>'
                    st.components.v1.html(iframe, height=1100)

                    # Download button
                    st.download_button(
                        "📥 Download Improved Resume (PDF)",
                        data=pdf_stream,
                        file_name=f"improved_resume_{job_role.replace(' ', '_').lower()}.pdf",
                        mime="application/pdf"
                    )
            else:
                st.warning("Resume text not available.")
        except Exception as e:
            st.error(f"Error generating improved resume: {e}")

    with tab3:
        if st.session_state.get("resume_file_bytes"):
            display_resume_highlights(
                strengths=feedback.highlighted_strengths or [],
                weaknesses=feedback.highlighted_weaknesses or []
            )

            pdf_bytes = io.BytesIO(st.session_state.resume_file_bytes)

            highlighted_pdf = highlight_resume_pdf_keywords(
                pdf_bytes,
                strengths=feedback.highlighted_strengths or [],
                weaknesses=feedback.highlighted_weaknesses or []
            )

            # Display in Streamlit
            b64_pdf = base64.b64encode(highlighted_pdf.getvalue()).decode("utf-8")
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="700" height="1000"></iframe>'
            st.components.v1.html(pdf_display, height=1100, scrolling=True)

            # Download button
            st.download_button(
                label="📥 Download Highlighted Resume",
                data=highlighted_pdf.getvalue(),
                file_name="highlighted_resume.pdf",
                mime="application/pdf"
            )

        elif st.session_state.get("resume_text"):
            # For text input, just show highlighted strengths/weaknesses
            st.info("⚠️ Highlighted PDF is only available when you upload a resume file.")
            st.subheader("✅ Strengths")
            for s in feedback.highlighted_strengths or []:
                st.success(f"- {s}")
            st.subheader("❌ Weaknesses")
            for w in feedback.highlighted_weaknesses or []:
                st.error(f"- {w}")

    
    with tab4:
        try:
            resume_text = None

            # Case 1: user pasted text
            if st.session_state.get("resume_text"):
                resume_text = st.session_state.resume_text

            # Case 2: user uploaded PDF (use cached bytes!)
            elif st.session_state.get("resume_file_bytes"):
                resume_text = extract_text_from_resume(io.BytesIO(st.session_state.resume_file_bytes))

            if resume_text:
                with st.spinner("✨ Comparing Resume with the Job Description..."):
                    st.header(f"📋 Resume vs Job Description for {job_role}")
                    if job_description.strip():
                        comparison = request_resume_comparison(resume_text, job_description, job_role)
                        
                        st.subheader("✅ Matched Skills")
                        if comparison["matched_skills"]:
                            for skill in comparison["matched_skills"]:
                                st.success(f"• {skill}")
                        else:
                            st.info("No exact matches found.")

                        st.subheader("❌ Missing Skills")
                        if comparison["missing_skills"]:
                            for skill in comparison["missing_skills"]:
                                st.error(f"• {skill}")
                        else:
                            st.info("No missing skills identified.")

                        st.subheader("💡 Recommendations")
                        if comparison["recommendations"]:
                            for rec in comparison["recommendations"]:
                                st.info(f"• {rec}")
                        else:
                            st.info("No additional recommendations provided.")
                    else:
                        st.warning("Please provide a job description to compare against.")
            else:
                st.warning("Resume text not available.")
        except Exception as e:
            st.error(f"Error generating resume comparison: {e}")



# Add instructions for first-time users
elif not st.session_state.resume_uploaded:
    st.info("👆 Upload your PDF resume and enter a target job role to get started!")
    st.markdown("""
    ### How it works:
    1. 📄 Upload your resume (PDF format)
    2. 🎯 Enter your target job role
    3. 📋 Optional: Paste the job description for better analysis
    4. ✨ Click "Analyze My Resume" to get AI-powered feedback
    5. 📊 Review your score and personalized recommendations
    """)

# Add footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 14px;'>"
    "Powered by AI Resume Reviewer • Uses Mistral LLM via Ollama"
    "</div>",
    unsafe_allow_html=True
)