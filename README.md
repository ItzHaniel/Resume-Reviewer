# requirements.txt
streamlit==1.49.1
pandas==2.2.2
plotly==5.24.1
pdfplumber==0.11.4
PyMuPDF==1.24.9
pydantic==2.9.2
langchain==0.3.0
langchain-ollama==0.3.7
ollama==0.5.3

# Setup Guide

## 1. Create and Activate a Virtual Environment (recommended)
```bash
python -m venv venv
source venv/bin/activate   # On Linux/Mac
venv\Scripts\activate      # On Windows
```

## 2. Install Dependencies
```bash
pip install -r requirements.txt
```

## 3. Run the App
```bash
streamlit run app2.py
```

This will launch the AI Resume Reviewer in your default web browser.

## 4. Notes
- Ensure **Ollama** is installed and running locally to use the LLM (Mistral model).
- Place your resume files in PDF format when uploading.
- Target job role is required; job description is optional but improves feedback.
