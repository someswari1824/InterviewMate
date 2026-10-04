# InterviewMate

A realistic local AI mock interview app using Streamlit, Ollama/Llama 3.2, Whisper and live camera recording (WebM).

## Flow
1. Enter candidate details and upload resume.
2. Select interview topics and total interview duration.
3. Start the interview.
4. Live camera + audio recording runs during the interview.
5. AI asks a question and reads it aloud using browser speech.
6. Candidate answers by typing or voice.
7. AI evaluates the answer.
8. The next question starts automatically. There is no per-question timer.
9. This continues until the overall interview timer reaches zero.
10. Interview results and recording are available after the interview.

## Run

### VS Code Terminal
```bash
pip install -r requirements.txt
streamlit run app.py
```

Allow camera and microphone permissions in the browser.


### Camera recording
The WebRTC camera records video + microphone audio to a local WebM file while the interview runs. Click START in the camera component when the interview begins and STOP when the interview ends to finalize the file.
