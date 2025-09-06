import json
from langchain.llms import Ollama
from langchain.prompts import PromptTemplate
from src.helpers.feedback import ResumeFeedback
from pydantic import ValidationError

llm = Ollama(model="mistral")

def build_prompt(resume_text: str, job_role: str, job_description:str | None = None) -> str:
    prompt = f"""
    You are an expert career coach, with over 20+ years of experience in the field of job hiring. Review the resume for the given target role: {job_role}
    - Analyze structure, content, and tone
    - Provide specific feedback such as:
      Missing skills or keywords relevant to the job, Recommendations to improve formatting or clarity, Highlighting redundant or vague language, Suggestions to tailor experience/achievements to the job role.
    - Score the resume out of 100.
    - Provide a set of 3 actionable steps to be taken.

    Resume:
    {resume_text}

    {job_description}

    Provide JSON output with keys:
    - summary: short paragraph analyzing structure, content, and tone; include
    formatting and clarity recommendations, vague/redundant language, and
    suggestions for tailoring achievements to the job role.
    - missing_skills (list)
    - weaknesses (list)
    - strengths (list) [provide the exact same text in the resume that represent strengths]
    - improvements (list)
    - score (0-100)

    **Important:** ONLY return JSON, no extra text.
    """

    return prompt

def get_resume_feedback(resume_text: str, job_role: str, job_description:str | None = None) -> str:
    prompt = build_prompt(resume_text, job_role, job_description)
    
    raw_output = llm(prompt)

    try: 
        json_output = json.loads(raw_output)
    except json.JSONDecodeError:    #quick fallback approach
        start = raw_output.find("{")
        end = raw_output.find("}")
        json_output = json.loads(raw_output[start:end])

    try: 
        feedback = ResumeFeedback(**json_output)
    except ValidationError as e:
        raise ValueError(f"LLM output could not be parsed: {e}")

    return feedback
