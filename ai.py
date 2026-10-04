import os
import streamlit as st
import ollama
from groq import Groq


def ask_with_ollama(prompt):
    response = ollama.chat(
        model="llama3.2:3b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]


def ask_with_groq(prompt):

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        try:
            api_key = st.secrets["GROQ_API_KEY"]
        except Exception:
            api_key = None

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. "
            "Add it in Streamlit Cloud → Settings → Secrets."
        )

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.4
    )

    return response.choices[0].message.content


def ask_ai(prompt):

    # -------------------------------------------------
    # LOCAL: Use Ollama
    # -------------------------------------------------

    try:
        return ask_with_ollama(prompt)

    except Exception:
        pass


    # -------------------------------------------------
    # CLOUD: Use Groq
    # -------------------------------------------------

    return ask_with_groq(prompt)