import re

from ai import ask_ai


def generate_question(
    candidate_name,
    role,
    interview_type,
    topics,
    resume_text,
    question_number,
    previous_questions
):
    """
    Generate one interview question.
    """

    topics_text = ", ".join(topics) if topics else "General technical topics"

    prompt = f"""
You are a professional technical interviewer.

Candidate name:
{candidate_name}

Target role:
{role}

Interview type:
{interview_type}

Question number:
{question_number}

Selected topics:
{topics_text}

Candidate resume:
{resume_text[:8000]}

Previous questions:
{previous_questions}

Your task:
Ask exactly ONE interview question.

Rules:
1. Ask only one question.
2. Do not provide the answer.
3. Do not provide explanation.
4. Do not provide multiple questions.
5. Keep the question suitable for a college student.
6. Prefer practical interview questions.
7. Connect the question to the candidate's resume when appropriate.
8. Gradually increase difficulty.
9. Do not repeat previous questions.
10. Return ONLY the question.

Example:
What is the difference between an ArrayList and a LinkedList in Java?
"""

    question = ask_ai(prompt).strip()

    # Remove accidental quotation marks
    question = question.strip('"').strip("'")

    return question


def evaluate_answer(question, answer):
    """
    Evaluate candidate answer.
    """

    prompt = f"""
You are a professional technical interviewer and answer evaluator.

Interview Question:
{question}

Candidate Answer:
{answer}

Evaluate the candidate's answer.

You MUST return the response in EXACTLY this format:

SCORE: X/10
CLARITY: X/10

CORRECT:
Explain what the candidate got right.

MISSING:
Explain important technical points that were missing.

IMPROVEMENT:
Explain how the candidate can improve the answer.

BETTER ANSWER:
Give a simple interview-ready answer.

IMPORTANT RULES:

1. SCORE must be an integer from 0 to 10.
2. CLARITY must be an integer from 0 to 10.
3. Never omit SCORE.
4. Never omit CLARITY.
5. Keep the feedback beginner-friendly.
6. Do not ask another question.
7. Evaluate only the candidate's answer.
8. Even if the answer is poor, still provide all sections.
"""

    feedback = ask_ai(prompt).strip()

    return feedback


def extract_score(text, label):
    """
    Extract SCORE or CLARITY from AI response.

    Supports formats such as:
    SCORE: 8/10
    SCORE - 8/10
    SCORE: 8
    CLARITY: 7/10
    """

    if not text:
        return 0

    pattern = rf"\b{re.escape(label)}\s*[:\-]\s*(10|[0-9])\s*(?:/\s*10)?\b"

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if match:
        score = int(match.group(1))

        return max(
            0,
            min(10, score)
        )

    return 0