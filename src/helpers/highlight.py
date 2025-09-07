import io
import fitz  # PyMuPDF
from typing import List, Union
import re

def highlight_resume_pdf(pdf_input: Union[str, io.BytesIO],
                         strengths: List[str],
                         gaps: List[str]) -> io.BytesIO:
    """
    Highlight strengths (green) and gaps/weaknesses (red) in a resume PDF.

    Args:
        pdf_input (str or BytesIO): File path or in-memory PDF bytes.
        strengths (List[str]): Keywords/phrases representing strengths.
        gaps (List[str]): Keywords/phrases representing gaps/weaknesses.

    Returns:
        BytesIO: In-memory PDF with highlights (ready for Streamlit display/download).
    """
    # Open PDF
    if isinstance(pdf_input, str):
        doc = fitz.open(pdf_input)
    elif isinstance(pdf_input, io.BytesIO):
        doc = fitz.open(stream=pdf_input.getvalue(), filetype="pdf")
    else:
        raise ValueError("pdf_input must be a file path or BytesIO object.")

    # Clean and prepare keywords
    def prepare_keywords(keywords):
        prepared = []
        for keyword in keywords:
            if not keyword.strip():
                continue
            # Remove special characters and split into words
            clean_keyword = re.sub(r'[^\w\s]', '', keyword.lower())
            words = clean_keyword.split()
            # Add both individual words and phrases
            for word in words:
                if len(word) > 3:  # Only words longer than 3 characters
                    prepared.append(word)
            if len(words) > 1:  # Also add the full phrase
                prepared.append(clean_keyword)
        return list(set(prepared))  # Remove duplicates

    clean_strengths = prepare_keywords(strengths)
    clean_gaps = prepare_keywords(gaps)

    # Helper function to highlight keywords
    def highlight_keywords(page, keywords, color):
        if not keywords:
            return
            
        text_instances = []
        for keyword in keywords:
            # Search for the keyword (case insensitive)
            areas = page.search_for(keyword)
            text_instances.extend(areas)
        
        # Highlight all found instances
        for area in text_instances:
            highlight = page.add_highlight_annot(area)
            highlight.set_colors(stroke=color)
            highlight.update()

    # Highlight strengths (green) and gaps (red)
    for page in doc:
        highlight_keywords(page, clean_strengths, color=(0, 1, 0))  # Green
        highlight_keywords(page, clean_gaps, color=(1, 0, 0))      # Red

    # Save to in-memory bytes
    output_stream = io.BytesIO()
    doc.save(output_stream, deflate=True, garbage=3)
    doc.close()
    output_stream.seek(0)

    return output_stream