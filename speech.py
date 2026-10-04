import os
import tempfile
import whisper

# Load Whisper once when the app starts.
model = whisper.load_model("base")


def transcribe_audio(audio_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
        temp.write(audio_bytes)
        audio_path = temp.name

    try:
        result = model.transcribe(audio_path, fp16=False)
        return result["text"].strip()
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
