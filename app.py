import streamlit as st
import io
import base64
from src.parsing.parser import extract_text_from_resume
from src.llm.reviewer import get_resume_feedback
from src.helpers.highlight import highlight_resume_pdf
from pydantic import ValidationError

st.title("AI Resume Reviewer")
resume = st.file_uploader("Upload your resume here", "pdf")

resume_text = ""
job_role = st.text_area("Enter your job role here.")
job_description = st.text_area("Enter your job description here.")


if st.button("Analyze"):
    if resume:
        resume_text = extract_text_from_resume(resume)
        resume.seek(0)  # reset pointer to start

    if not resume or not job_role:
        st.warning("Provide both resume and target job role.")
    else:
        with st.spinner("Generating AI feedback:"):
            feedback = get_resume_feedback(resume_text, job_role, job_description)

            try:
                st.subheader("Resume summary")
                st.info(feedback.summary)

                st.metric(label="Overall Score", value=f"{feedback.score}/100")
                col1, col2, col3 = st.columns(3)

                st.subheader("Strengths")
                for s in feedback.strengths:
                    st.markdown(f"- {s}")

                with col1:
                    st.markdown("### Missing Skills")
                    if feedback.missing_skills:
                        for skill in feedback.missing_skills:
                            st.markdown(f"- {skill}")
                    else:
                        st.markdown("✅ None detected")

                with col2:
                    st.markdown("### Weaknesses")
                    if feedback.weaknesses:
                        for weak in feedback.weaknesses:
                            st.markdown(f"- {weak}")
                    else:
                        st.markdown("✅ No major weaknesses")

                with col3:
                    st.markdown("### Improvements")
                    if feedback.improvements:
                        for imp in feedback.improvements:
                            st.markdown(f"- {imp}")
                    else:
                        st.markdown("✅ Already optimized")

            except (ValidationError, ValueError) as e:
                st.error(f"Error processing resume feedback: {e}")

            with open("temp_resume.pdf", "wb") as f:
                f.write(resume.read())
            resume.seek(0)
            pdf_bytes = io.BytesIO(resume.read())
            highlighted_pdf = highlight_resume_pdf(pdf_bytes, feedback.improvements, feedback.weaknesses)

            b64_pdf = base64.b64encode(highlighted_pdf.getvalue()).decode("utf-8")
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
            st.components.v1.html(pdf_display, height=1100, scrolling=True)

            with open("highlighted_resume.pdf", "rb") as f:
                st.download_button(
                    label="Download Highlighted Resume",
                    data=f,
                    file_name="highlighted_resume.pdf",
                    mime="application/pdf"
                )