import fitz
import io
from typing import List, Union

def highlight_resume_pdf_keywords(pdf_input: Union[str, io.BytesIO],
                                  strengths: List[str],
                                  weaknesses: List[str]) -> io.BytesIO:
    # Open PDF
    if isinstance(pdf_input, str):
        doc = fitz.open(pdf_input)
    else:
        pdf_input.seek(0)
        doc = fitz.open(stream=pdf_input.read(), filetype="pdf")
    
    # Highlight strengths
    for page in doc:
        for word in strengths:
            for inst in page.search_for(word):
                h = page.add_highlight_annot(inst)
                h.set_colors(stroke=(0,1,0))  # green
                h.update()
    
    # Highlight weaknesses
    for page in doc:
        for word in weaknesses:
            for inst in page.search_for(word):
                h = page.add_highlight_annot(inst)
                h.set_colors(stroke=(1,0,0))  # red
                h.update()
    
    # Save to in-memory bytes
    output = io.BytesIO()
    doc.save(output)
    doc.close()
    output.seek(0)
    return output
