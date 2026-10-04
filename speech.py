import os
import tempfile
import whisper


# Load Whisper model once
model = whisper.load_model("small")


def transcribe_audio(audio_bytes):
    """
    Convert recorded audio into text.
    """

    if not audio_bytes:
        return ""

    # Save recorded audio temporarily
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".wav"
    ) as temp:
        temp.write(audio_bytes)
        audio_path = temp.name

    try:
        result = model.transcribe(
            audio_path,

            # Interview answers are in English
            language="en",

            # We want transcription, not translation
            task="transcribe",

            # Better for CPU
            fp16=False,

            # More deterministic transcription
            temperature=0,

            # Avoid previous text affecting the current answer
            condition_on_previous_text=False,

            # Help Whisper recognize technical words
            initial_prompt=(
                "This is a technical software engineering interview. "
                "The candidate may talk about Java, Python, SQL, DBMS, "
                "operating systems, computer networks, Docker, APIs, "
                "Spring Boot, REST APIs, Git, GitHub, programming, "
                "object oriented programming, databases and software development."
            )
        )

        text = result.get("text", "").strip()

        return text

    finally:
        # Delete temporary audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)