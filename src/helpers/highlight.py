import io
import fitz  # PyMuPDF
from typing import List, Union

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
        doc = fitz.open(stream=pdf_input, filetype="pdf")
    else:
        raise ValueError("pdf_input must be a file path or BytesIO object.")

    # Helper function to highlight a list of keywords with a given color
    def highlight_words(page, keywords: List[str], color: tuple):
        page_text = page.get_text("text").lower()  # normalize for case-insensitive
        for word in keywords:
            word_lower = word.lower()
            quads = page.search_for(word_lower, quads=True)  # precise coordinates
            for quad in quads:
                h = page.add_highlight_annot(quad)
                h.set_colors(stroke=color)
                h.update()

    # Highlight strengths (green)
    for page in doc:
        highlight_words(page, strengths, color=(0, 1, 0))

    # Highlight gaps/weaknesses (red)
    for page in doc:
        highlight_words(page, gaps, color=(1, 0, 0))

    # Save to in-memory bytes
    output_stream = io.BytesIO()
    doc.save(output_stream)
    doc.close()
    output_stream.seek(0)

    return output_stream
