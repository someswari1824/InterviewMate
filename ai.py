import ollama

MODEL = "llama3.2:3b"


def ask_ai(prompt):
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]
