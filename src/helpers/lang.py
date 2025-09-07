from langdetect import detect

def get_resume_language(resume_text):
    try:
        return detect(resume_text)
    except:
        return "en"  # default to English