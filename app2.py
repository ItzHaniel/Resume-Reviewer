# app2.py
import io
import base64
import re
import streamlit as st
import pandas as pd
import plotly.express as px
from pydantic import ValidationError

# local project imports
try:
    from src.parsing.parser import extract_text_from_resume
    from src.llm.reviewer import get_resume_feedback
    from src.helpers.highlight import highlight_resume_pdf
except ImportError:
    # Fallback for direct execution
    from parsing.parser import extract_text_from_resume
    from llm.reviewer import get_resume_feedback
    from helpers.highlight import highlight_resume_pdf

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

def find_contextual_matches(resume_text, feedback_items, item_type):
    """Find actual contextual matches in the resume text"""
    matches = []
    
    for item in feedback_items:
        if not item or len(item.strip()) < 3:
            continue
            
        # Clean the feedback item
        clean_item = re.sub(r'[^\w\s]', '', item.lower()).strip()
        if len(clean_item) < 3:
            continue
            
        # Split into words for better matching
        words = clean_item.split()
        
        # Look for this pattern in the resume text
        pattern = re.compile(re.escape(clean_item), re.IGNORECASE)
        found_matches = pattern.finditer(resume_text)
        
        for match in found_matches:
            # Get some context around the match
            start = max(0, match.start() - 50)
            end = min(len(resume_text), match.end() + 50)
            context = resume_text[start:end]
            
            # Clean up context boundaries
            if start > 0:
                # Find the start of a word or sentence
                context_start = max(0, context.find(' ') if ' ' in context else 0)
                context = context[context_start:]
            if end < len(resume_text):
                # Find the end of a word or sentence
                context_end = context.rfind(' ') if ' ' in context else len(context)
                context = context[:context_end]
                
            matches.append({
                'item': item,
                'context': context.strip(),
                'position': match.start()
            })
    
    return matches

def create_better_highlight_view(resume_text, strengths, weaknesses):
    """Create a better highlight view that shows contextual matches"""
    if not resume_text:
        return "<div>No resume text available</div>"
    
    # Find actual contextual matches
    strength_matches = find_contextual_matches(resume_text, strengths, 'strength')
    weakness_matches = find_contextual_matches(resume_text, weaknesses, 'weakness')
    
    html_output = "<div class='highlight-container'>"
    
    if strength_matches or weakness_matches:
        # Show contextual matches
        html_output += "<h3 style='color: #F8F8F8;'>Contextual Highlights Found in Resume</h3>"
        
        if strength_matches:
            html_output += "<h4 style='color: #90EE90;'>✅ Strengths Found:</h4>"
            for match in strength_matches[:5]:  # Show first 5 matches
                highlighted_context = match['context'].replace(
                    match['item'], 
                    f"<span class='highlight-strength'>{match['item']}</span>"
                )
                html_output += f"<div class='context-box context-strength'>{highlighted_context}</div>"
        
        if weakness_matches:
            html_output += "<h4 style='color: #FFB6C1;'>❌ Areas for Improvement Found:</h4>"
            for match in weakness_matches[:5]:  # Show first 5 matches
                highlighted_context = match['context'].replace(
                    match['item'], 
                    f"<span class='highlight-weakness'>{match['item']}</span>"
                )
                html_output += f"<div class='context-box context-weakness'>{highlighted_context}</div>"
        
        # Show full resume text without crazy highlighting
        html_output += "<h4 style='color: #F8F8F8; margin-top: 20px;'>Full Resume Text:</h4>"
        html_output += f"<pre style='white-space: pre-wrap; color: #CCCCCC;'>{resume_text}</pre>"
        
    else:
        # No matches found, just show the text
        html_output += "<p style='color: #CCCCCC;'>No specific matches found in resume text. Showing full resume:</p>"
        html_output += f"<pre style='white-space: pre-wrap; color: #CCCCCC;'>{resume_text}</pre>"
    
    html_output += "</div>"
    return html_output

st.title("📄 AI Resume Reviewer")
st.markdown("### Get a professional, data-driven analysis of your resume in seconds.")
st.markdown("---")

with st.expander("🚀 Upload & Analyze Your Resume", expanded=True):
    col_file, col_role = st.columns([1, 1.5])
    with col_file:
        resume = st.file_uploader("Upload your resume (PDF)", type="pdf", key="resume_uploader")
        if resume:
            st.session_state.resume_uploaded = True
            st.session_state.resume_file = resume
    with col_role:
        job_role = st.text_input("Target Job Role", placeholder="e.g., Senior Data Scientist", key="job_role_input")
        job_description = st.text_area("Job Description (optional)", placeholder="Paste the job description here for a more tailored analysis.", key="job_desc_input")

    st.markdown("---")

    if st.button("✨ Analyze My Resume", key="analyze_btn"):
        if not resume:
            st.warning("Please upload your resume (PDF) before analyzing.")
        elif not job_role or job_role.strip() == "":
            st.warning("Please enter a target job role (this is required).")
        else:
            try:
                with st.spinner("⏳ Generating AI feedback..."):
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

    tab1, tab2, tab3 = st.tabs(["📊 Overview & Metrics", "📄 Resume Analysis", "🔍 Contextual View"])

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
        st.header("Resume Analysis")
        
        try:
            # Get the resume file from session state
            resume_file = st.session_state.resume_file
            if resume_file:
                # Reset file pointer
                resume_file.seek(0)
                pdf_bytes = io.BytesIO(resume_file.read())
                
                # Generate highlighted PDF
                highlighted_pdf = highlight_resume_pdf(pdf_bytes, feedback.strengths or [], feedback.weaknesses or [])
                
                # Display download button
                st.download_button(
                    label="📥 Download Highlighted PDF",
                    data=highlighted_pdf.getvalue(),
                    file_name=f"highlighted_resume_{job_role.replace(' ', '_').lower()}.pdf",
                    mime="application/pdf",
                    help="Download the resume with strengths (green) and areas to improve (red) highlighted"
                )
                
                st.markdown("---")
                
                # Better highlight preview
                st.subheader("Resume Text Analysis")
                st.info("💡 This shows where specific strengths and areas for improvement were found in your resume:")
                
                html_content = create_better_highlight_view(
                    st.session_state.resume_text, 
                    feedback.strengths or [], 
                    feedback.weaknesses or []
                )
                
                st.components.v1.html(html_content, height=800, scrolling=True)
                    
            else:
                st.warning("Resume file not available for analysis.")
                
        except Exception as e:
            st.error(f"Error processing resume: {e}")
            st.info("Try downloading the PDF for the best highlighting experience.")

    with tab3:
        st.header("Contextual View")
        st.info("Here's a clearer view of how your resume content relates to the feedback:")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("✅ Strength Analysis")
            if feedback.strengths:
                strength_matches = find_contextual_matches(st.session_state.resume_text, feedback.strengths, 'strength')
                if strength_matches:
                    for i, match in enumerate(strength_matches[:8]):
                        st.success(f"""
                        **Strength #{i+1}: {match['item']}**
                        ```
                        {match['context']}
                        ```
                        """)
                else:
                    st.info("The AI identified these strengths, but they may be conceptual rather than specific phrases in your resume:")
                    for strength in feedback.strengths[:5]:
                        st.success(f"• {strength}")
            else:
                st.info("No strengths identified")
        
        with col2:
            st.subheader("❌ Improvement Analysis")
            if feedback.weaknesses:
                weakness_matches = find_contextual_matches(st.session_state.resume_text, feedback.weaknesses, 'weakness')
                if weakness_matches:
                    for i, match in enumerate(weakness_matches[:8]):
                        st.error(f"""
                        **Area #{i+1}: {match['item']}**
                        ```
                        {match['context']}
                        ```
                        """)
                else:
                    st.info("The AI identified these areas for improvement, but they may be conceptual rather than specific phrases:")
                    for weakness in feedback.weaknesses[:5]:
                        st.error(f"• {weakness}")
            else:
                st.info("No areas for improvement identified")

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