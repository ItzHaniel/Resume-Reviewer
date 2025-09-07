from pydantic import BaseModel
from typing import List

class ResumeFeedback(BaseModel):
    summary: str
    missing_skills: List[str]
    weaknesses: List[str]
    strengths: List[str]
    improvements: List[str]
    highlighted_strengths: List[str] 
    highlighted_weaknesses: List[str] 
    score: int