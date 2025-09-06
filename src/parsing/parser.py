import pdfplumber

def extract_text_from_resume(resume) -> str: 
    extracted_text = []
    with pdfplumber.open(resume) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                extracted_text.append(page_text)
    return "\n\n".join(extracted_text).strip()