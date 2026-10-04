import re
from ai import ask_ai


def generate_question(candidate_name, role, interview_type, topics, resume_text, question_number, previous_questions):
    topics_text = ", ".join(topics)
    previous_text = "\n".join(previous_questions[-8:]) if previous_questions else "None"

    prompt = f"""
You are a professional technical interviewer conducting a mock interview.

Candidate: {candidate_name}
Target role: {role}
Interview type: {interview_type}
Question number: {question_number}
Selected topics: {topics_text}

Resume:
{resume_text[:8000]}

Previous questions:
{previous_text}

Ask exactly ONE interview question.
Rules:
- Do not give the answer.
- Make it suitable for a college placement interview.
- Prefer practical questions and real-world examples.
- For resume-based interviews, use the candidate's skills/projects when useful.
- Increase difficulty gradually.
- Do not repeat previous questions.
- Return only the question.
"""
    return ask_ai(prompt).strip()


def evaluate_answer(question, answer):
    prompt = f"""
You are a professional technical interview evaluator.

Question:
{question}

Candidate answer:
{answer}

Evaluate the answer using EXACTLY this format:

SCORE: X/10
CLARITY: X/10

CORRECT:
What the candidate got right.

MISSING:
Important points that were missing or incorrect.

IMPROVEMENT:
How the candidate can improve.

BETTER ANSWER:
A simple, interview-ready answer.

Keep the explanation beginner-friendly and concise.
"""
    return ask_ai(prompt).strip()


def extract_score(text, label):
    match = re.search(rf"{re.escape(label)}\s*:\s*(\d+)\s*/\s*10", text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def generate_follow_up(question, answer):
    prompt = f"""
You are a technical interviewer.

Original question:
{question}

Candidate answer:
{answer}

Ask exactly ONE short follow-up question that checks real understanding.
Do not give the answer. Return only the question.
"""
    return ask_ai(prompt).strip()
