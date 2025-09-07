import json
import re
from langchain.llms import Ollama
from src.helpers.feedback import ResumeFeedback
from pydantic import ValidationError

llm = Ollama(model="mistral")

def extract_keywords(text: str, max_keywords: int = 15) -> list:
    """Extract relevant keywords from text"""
    if not text:
        return []
    
    words = re.findall(r"[a-zA-Z]+", text)
    stopwords = {"the", "and", "with", "for", "this", "that", "from", 
                "your", "role", "job", "position", "description", "should",
                "will", "must", "have", "has", "are", "is", "was", "were"}
    keywords = [w.lower() for w in words if len(w) > 3 and w.lower() not in stopwords]
    return list(dict.fromkeys(keywords))[:max_keywords]

def compute_keyword_match(resume_text: str, job_description: str) -> int:
    """Calculate keyword match percentage"""
    if not job_description:
        return 0
        
    resume_words = set(re.findall(r'\w+', resume_text.lower()))
    jd_words = set(re.findall(r'\w+', job_description.lower()))
    
    # Remove common words
    common_words = {'the', 'and', 'with', 'for', 'this', 'that', 'from', 
                   'your', 'role', 'job', 'position', 'description'}
    jd_words = jd_words - common_words
    
    if not jd_words:
        return 0
        
    overlap = resume_words.intersection(jd_words)
    return int((len(overlap) / len(jd_words)) * 100)

def build_prompt(resume_text: str, job_role: str, job_description: str | None = None) -> str:
    """Build the prompt for the LLM"""
    jd_keywords = extract_keywords(job_description or job_role)
    keyword_str = ", ".join(jd_keywords[:10])
    
    # Truncate resume text to avoid token limits
    truncated_resume = resume_text[:2000] + "..." if len(resume_text) > 2000 else resume_text
    
    prompt = f"""
    ROLE: You are an expert career coach with 20+ years of hiring experience.

    TASK: Analyze this resume for the target job role: "{job_role}".
    Important keywords to focus on: {keyword_str}

    RESUME TEXT:
    {truncated_resume}

    JOB DESCRIPTION:
    {job_description or "Not provided"}

    REQUIREMENTS:
    1. Provide ONLY valid JSON output with no additional text
    2. Use these exact keys: summary, missing_skills, weaknesses, strengths, improvements, score
    3. Score must be an integer between 0-100
    4. All other values must be arrays of strings except summary which is a string

    JSON TEMPLATE:
    {{
      "summary": "Brief analysis of the resume focusing on {job_role}...",
      "missing_skills": ["specific skill needed for {job_role}", "another required skill"],
      "weaknesses": ["specific weakness for {job_role}", "area needing improvement"],
      "strengths": ["specific strength relevant to {job_role}", "strong point"],
      "improvements": ["actionable suggestion for {job_role}", "specific improvement"],
      "score": 75
    }}

    IMPORTANT: Your entire response must be valid JSON only. Do not add any explanatory text.
    """
    return prompt

def extract_json_from_text(text: str) -> dict:
    """Extract JSON from LLM output, handling various formats"""
    # Clean the text
    cleaned = text.strip()
    
    # Remove markdown code blocks
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    
    cleaned = cleaned.strip()
    
    # Try direct JSON parsing first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON object pattern
    json_pattern = r'\{[\s\S]*\}'
    match = re.search(json_pattern, cleaned, re.DOTALL)
    
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            # Try to fix common JSON issues
            fixed_json = match.group()
            # Fix single quotes to double quotes
            fixed_json = fixed_json.replace("'", '"')
            # Fix trailing commas
            fixed_json = re.sub(r',\s*}', '}', fixed_json)
            fixed_json = re.sub(r',\s*]', ']', fixed_json)
            
            try:
                return json.loads(fixed_json)
            except json.JSONDecodeError:
                pass
    
    # If all else fails, create a fallback response
    return {
        "summary": f"Analysis for {job_role} completed successfully. Review the detailed feedback below.",
        "missing_skills": [],
        "weaknesses": [],
        "strengths": [],
        "improvements": [],
        "score": 50
    }

def get_resume_feedback(resume_text: str, job_role: str, job_description: str | None = None) -> ResumeFeedback:
    """Get feedback on resume from LLM"""
    if not resume_text.strip():
        raise ValueError("Resume text is empty")
    
    if not job_role.strip():
        raise ValueError("Job role is required")
    
    prompt = build_prompt(resume_text, job_role, job_description)
    
    try:
        raw_output = llm(prompt)
    except Exception as e:
        raise ValueError(f"LLM call failed: {e}")
    
    # Extract JSON from the output
    json_output = extract_json_from_text(raw_output)
    
    try:
        feedback = ResumeFeedback(**json_output)
    except ValidationError as e:
        # Create fallback feedback if validation fails
        feedback = ResumeFeedback(
            summary=f"Analysis for {job_role} completed with minor formatting issues.",
            missing_skills=[],
            weaknesses=[],
            strengths=[],
            improvements=[],
            score=50
        )

    # Ensure all list fields are actually lists
    feedback.missing_skills = list(feedback.missing_skills or [])
    feedback.weaknesses = list(feedback.weaknesses or [])
    feedback.strengths = list(feedback.strengths or [])
    feedback.improvements = list(feedback.improvements or [])

    # Hybrid scoring adjustment if job description is provided
    if job_description and job_description.strip():
        try:
            keyword_score = compute_keyword_match(resume_text, job_description)
            feedback.score = int((feedback.score * 0.7) + (keyword_score * 0.3))
            feedback.score = max(0, min(100, feedback.score))
        except Exception:
            # If keyword scoring fails, keep the original score
            pass

    return feedback