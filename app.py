import os
import re
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from pypdf import PdfReader

from ai import ask_ai
from speech import transcribe_audio
from question import generate_question, evaluate_answer, extract_score, generate_follow_up

try:
    from streamlit_webrtc import WebRtcMode, webrtc_streamer
    from aiortc.contrib.media import MediaRecorder
    WEBRTC_AVAILABLE = True
except Exception:
    WEBRTC_AVAILABLE = False

st.set_page_config(page_title="InterviewMate", page_icon="🎯", layout="wide")

# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------

def init_state():
    defaults = {
        "candidate_name": "",
        "role": "Software Developer",
        "interview_type": "Resume Based",
        "resume_text": "",
        "resume_topics": [],
        "selected_topics": [],
        "question": "",
        "question_number": 0,
        "question_history": [],
        "technical_scores": [],
        "clarity_scores": [],
        "feedback": "",
        "current_answer": "",
        "last_voice_answer": "",
        "follow_up": "",
        "interview_started": False,
        "interview_finished": False,
        "interview_end_time": 0.0,
        "interview_duration_seconds": 600,
        "recording_path": "",
        "recording_ready": False,
        "last_question_spoken": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_state()

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def extract_resume_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages).strip()


def extract_topics(resume_text):
    prompt = f"""
Read this resume and identify technical interview topics.

Resume:
{resume_text[:10000]}

Return ONLY a comma-separated list.
Examples: Java, Python, OOP, SQL, DBMS, Operating Systems,
Computer Networks, Git, Docker, Spring Boot, REST APIs, Projects.
"""
    raw = ask_ai(prompt)
    return [x.strip() for x in raw.split(",") if x.strip()]


def reset_interview():
    st.session_state.question = ""
    st.session_state.question_number = 0
    st.session_state.question_history = []
    st.session_state.technical_scores = []
    st.session_state.clarity_scores = []
    st.session_state.feedback = ""
    st.session_state.current_answer = ""
    st.session_state.last_voice_answer = ""
    st.session_state.follow_up = ""
    st.session_state.interview_started = False
    st.session_state.interview_finished = False
    st.session_state.interview_end_time = 0.0
    st.session_state.recording_ready = False
    st.session_state.last_question_spoken = ""


def ask_next_question():
    with st.spinner("🤖 AI interviewer is thinking..."):
        q = generate_question(
            st.session_state.candidate_name,
            st.session_state.role,
            st.session_state.interview_type,
            st.session_state.selected_topics,
            st.session_state.resume_text,
            st.session_state.question_number,
            [x["question"] for x in st.session_state.question_history],
        )
    st.session_state.question = q
    st.session_state.last_question_spoken = ""


def speak_question(text):
    safe_text = text.replace("\\", "\\\\").replace("`", "\\`").replace("</", "<\\/")
    components.html(
        f"""
        <script>
        const text = `{safe_text}`;
        if ('speechSynthesis' in window && text) {{
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 0.92;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;
            window.speechSynthesis.speak(utterance);
        }}
        </script>
        """,
        height=0,
    )


def remaining_seconds():
    return max(0, int(st.session_state.interview_end_time - time.time()))


def finish_interview():
    st.session_state.interview_started = False
    st.session_state.interview_finished = True
    st.session_state.feedback = ""
    st.session_state.current_answer = ""
    st.session_state.follow_up = ""


def show_live_camera():
    if not WEBRTC_AVAILABLE:
        st.error("Live camera requires streamlit-webrtc. Install requirements.txt first.")
        return None

    recording_dir = Path("recordings")
    recording_dir.mkdir(exist_ok=True)
    recording_path = recording_dir / "InterviewMate_interview.webm"

    def recorder_factory():
        return MediaRecorder(str(recording_path))

    ctx = webrtc_streamer(
        key="interview-camera-recorder",
        mode=WebRtcMode.SENDRECV,
        media_stream_constraints={"video": True, "audio": True},
        in_recorder_factory=recorder_factory,
        rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
        media_toggle_controls=True,
    )
    st.session_state.webrtc_ctx = ctx
    st.session_state.recording_path = str(recording_path)
    return ctx


def timer_panel(end_time):
    @st.fragment(run_every="1s")
    def _timer():
        remaining = max(0, int(end_time - time.time()))
        minutes, seconds = divmod(remaining, 60)
        label = f"{minutes:02d}:{seconds:02d}"
        if remaining <= 30:
            box_class = "danger"
        else:
            box_class = "normal"
        st.markdown(
            f"""
            <div class=\"timer-badge {box_class}\">⏱ {label}</div>
            <style>
            .timer-badge {{
                position: fixed;
                top: 90px;
                right: 28px;
                z-index: 9999;
                padding: 9px 16px;
                border-radius: 999px;
                color: white;
                font-size: 20px;
                font-weight: 800;
                box-shadow: 0 3px 14px rgba(0,0,0,.25);
            }}
            .normal {{ background:#111827; }}
            .danger {{ background:#dc2626; }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        if remaining <= 0 and st.session_state.interview_started:
            finish_interview()
            st.rerun()
    _timer()

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("🎯 InterviewMate")
st.write("A realistic local AI mock interview that keeps going until your interview time ends.")
st.caption("Streamlit • Ollama • Llama 3.2 • Whisper • Live Camera • Browser Voice")

# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

st.sidebar.title("⚙️ Interview Settings")

roles = ["Software Developer", "Java Developer", "Python Developer", "Full Stack Developer", "Data Analyst", "Other"]
role = st.sidebar.selectbox("💼 Target Role", roles, index=roles.index(st.session_state.role))
st.session_state.role = role

core_subjects = st.sidebar.multiselect(
    "📚 Core Subjects",
    ["Java", "Python", "OOP", "DSA", "SQL", "DBMS", "Operating Systems", "Computer Networks", "Computer Architecture", "Web Technologies"],
    default=["Java", "OOP", "SQL", "DBMS"],
)

interview_types = ["Resume Based", "Core Subjects", "Mixed Interview", "Full Mock Interview"]
interview_type = st.sidebar.selectbox("🎤 Interview Type", interview_types, index=interview_types.index(st.session_state.interview_type))
st.session_state.interview_type = interview_type

duration_option = st.sidebar.selectbox("⏱️ Total Interview Time", ["5 minutes", "10 minutes", "15 minutes", "20 minutes", "Custom"])
if duration_option == "Custom":
    duration_minutes = st.sidebar.number_input("Minutes", min_value=1, max_value=60, value=10)
else:
    duration_minutes = int(duration_option.split()[0])

st.sidebar.info("There is NO time limit per question. The timer is for the entire interview.")
camera_enabled = st.sidebar.checkbox("📷 Camera + Recording", value=True)

# ---------------------------------------------------------
# CANDIDATE / RESUME
# ---------------------------------------------------------

st.header("👤 Candidate Details")
name = st.text_input("Enter your name", value=st.session_state.candidate_name, placeholder="Example: Someswari")
if name.strip():
    st.session_state.candidate_name = name.strip()

if not st.session_state.interview_started:
    st.header("📄 Upload Your Resume")
    resume = st.file_uploader("Upload your resume PDF", type=["pdf"])
    if resume is not None:
        try:
            resume_text = extract_resume_text(resume)
            st.session_state.resume_text = resume_text
            st.success("✅ Resume uploaded successfully!")
            if not st.session_state.resume_topics:
                with st.spinner("🤖 AI is analyzing your resume..."):
                    st.session_state.resume_topics = extract_topics(resume_text)
            resume_selected = st.multiselect(
                "🧠 Choose resume topics you want to practice",
                st.session_state.resume_topics,
                default=st.session_state.resume_topics,
            )
            st.session_state.selected_topics = resume_selected
            with st.expander("👀 View Extracted Resume Text"):
                st.text(resume_text)
        except Exception as exc:
            st.error("❌ Could not read the resume.")
            st.exception(exc)
            resume_selected = []
    else:
        resume_selected = []

    if interview_type == "Resume Based":
        selected_topics = resume_selected
    elif interview_type == "Core Subjects":
        selected_topics = core_subjects
    else:
        selected_topics = list(dict.fromkeys(resume_selected + core_subjects))
    st.session_state.selected_topics = selected_topics

    if selected_topics:
        st.info("Selected topics: " + ", ".join(selected_topics))
    else:
        st.warning("Please select at least one interview topic.")

    st.divider()
    if st.button("🚀 Start Realistic Interview", use_container_width=True):
        if not st.session_state.candidate_name:
            st.warning("⚠️ Please enter your name first.")
        elif not selected_topics:
            st.warning("⚠️ Please select at least one interview topic.")
        elif camera_enabled and not WEBRTC_AVAILABLE:
            st.error("Install the requirements first so the camera/recording can work.")
        else:
            reset_interview()
            st.session_state.interview_started = True
            st.session_state.interview_duration_seconds = int(duration_minutes * 60)
            st.session_state.interview_end_time = time.time() + st.session_state.interview_duration_seconds
            st.session_state.question_number = 1
            ask_next_question()
            st.rerun()

# ---------------------------------------------------------
# LIVE INTERVIEW
# ---------------------------------------------------------

if st.session_state.interview_started:
    timer_panel(st.session_state.interview_end_time)

    st.divider()
    st.header("🎤 Live AI Interview")
    st.caption("There is no per-question timer. Finish your answer and submit it; the AI will evaluate it and immediately ask the next question. The interview ends when the overall timer reaches 00:00.")

    left_col, right_col = st.columns([2.2, 1])

    with left_col:
        st.subheader(f"❓ Question {st.session_state.question_number}")
        st.info(st.session_state.question)

        if st.session_state.question != st.session_state.last_question_spoken:
            speak_question(st.session_state.question)
            st.session_state.last_question_spoken = st.session_state.question

        if st.button("🔊 Repeat Question"):
            speak_question(st.session_state.question)

        st.subheader("✍️ Your Answer")
        answer = st.text_area("Type your answer", value=st.session_state.last_voice_answer, height=150, placeholder="Type your answer here...")

        st.subheader("🎤 Or Answer by Voice")
        audio = st.audio_input("Record your answer")
        if audio is not None:
            with st.spinner("🎧 Converting your voice to text..."):
                try:
                    voice_answer = transcribe_audio(audio.getvalue())
                    st.session_state.last_voice_answer = voice_answer
                    answer = voice_answer
                    st.success("✅ Voice converted successfully!")
                    st.write("**Transcribed:**", voice_answer)
                except Exception as exc:
                    st.error("❌ Could not convert voice to text.")
                    st.exception(exc)

        if st.button("✅ Complete Answer → Next Question", use_container_width=True):
            if remaining_seconds() <= 0:
                finish_interview()
                st.rerun()
            elif not answer.strip():
                st.warning("⚠️ Please answer the question first.")
            else:
                st.session_state.current_answer = answer
                with st.spinner("🤖 Interviewer is evaluating your answer..."):
                    feedback = evaluate_answer(st.session_state.question, answer)
                tech = extract_score(feedback, "SCORE")
                clarity = extract_score(feedback, "CLARITY")
                st.session_state.feedback = feedback
                st.session_state.technical_scores.append(tech)
                st.session_state.clarity_scores.append(clarity)
                st.session_state.question_history.append({
                    "question": st.session_state.question,
                    "answer": answer,
                    "technical_score": tech,
                    "clarity_score": clarity,
                    "feedback": feedback,
                })

                # Real-interview behavior: after completing an answer, move directly to another question.
                if remaining_seconds() > 0:
                    st.session_state.question_number += 1
                    st.session_state.feedback = ""
                    st.session_state.follow_up = ""
                    st.session_state.current_answer = ""
                    st.session_state.last_voice_answer = ""
                    ask_next_question()
                    st.rerun()
                else:
                    finish_interview()
                    st.rerun()

    with right_col:
        st.subheader("📷 Live Camera")
        st.caption("Camera is recorded while the interview is running.")
        if camera_enabled:
            try:
                show_live_camera()
            except Exception as exc:
                st.error("❌ Camera could not start. Allow camera access in the browser.")
                st.exception(exc)
        else:
            st.warning("Camera is OFF")

        # Visible timer next to the camera, plus the fixed badge in the top-right corner.
        remaining = remaining_seconds()
        mins, secs = divmod(remaining, 60)
        st.markdown(
            f"<div style='text-align:center;margin-top:8px;padding:8px;border-radius:12px;background:#111827;color:white;font-size:24px;font-weight:800;'>⏱ {mins:02d}:{secs:02d}</div>",
            unsafe_allow_html=True,
        )
        st.caption("Overall interview time")

    st.divider()
    if st.button("🛑 End Interview Now", use_container_width=True):
        finish_interview()
        st.rerun()

# ---------------------------------------------------------
# FINISHED / DASHBOARD
# ---------------------------------------------------------

if st.session_state.interview_finished:
    st.success("🏁 Interview completed! The overall interview time is finished or you ended the interview.")
    if st.session_state.recording_path and os.path.exists(st.session_state.recording_path):
        with open(st.session_state.recording_path, "rb") as video_file:
            st.download_button(
                "🎥 Download Interview Recording",
                data=video_file.read(),
                file_name="InterviewMate_interview.webm",
                mime="video/webm",
                use_container_width=True,
            )
    st.info("If the recording button is not available yet, click STOP on the camera component first so the recorder can finish writing the video file, then click the page refresh button.")

if st.session_state.technical_scores:
    st.divider()
    st.header("📊 Interview Dashboard")
    tech = st.session_state.technical_scores
    clarity = st.session_state.clarity_scores
    avg_tech = sum(tech) / len(tech)
    avg_clarity = sum(clarity) / len(clarity)
    overall = (avg_tech + avg_clarity) / 2

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Technical", f"{avg_tech:.1f}/10")
    c2.metric("Clarity", f"{avg_clarity:.1f}/10")
    c3.metric("Overall", f"{overall:.1f}/10")
    c4.metric("Questions", len(tech))

    st.write("Technical Knowledge")
    st.progress(min(avg_tech / 10, 1.0))
    st.write("Communication / Clarity")
    st.progress(min(avg_clarity / 10, 1.0))
    st.write("Overall Performance")
    st.progress(min(overall / 10, 1.0))

    if overall >= 8:
        st.success("Excellent! Keep practicing advanced questions.")
    elif overall >= 6:
        st.info("Good performance. Improve clarity and add practical examples.")
    elif overall >= 4:
        st.warning("Basic understanding is present. Revise fundamentals and practice speaking.")
    else:
        st.error("More preparation is needed. Start with fundamentals and practice simple questions.")

    st.subheader("📝 Interview History")
    for i, item in enumerate(st.session_state.question_history, 1):
        with st.expander(f"Question {i} — Technical {item['technical_score']}/10"):
            st.write("### ❓ Question")
            st.write(item["question"])
            st.write("### 💬 Your Answer")
            st.write(item["answer"])
            st.write(f"**Technical:** {item['technical_score']}/10")
            st.write(f"**Clarity:** {item['clarity_score']}/10")
            st.write("### 📋 Feedback")
            st.write(item.get("feedback", ""))

    if st.button("🔁 Start New Interview", use_container_width=True):
        reset_interview()
        st.rerun()

st.divider()
st.caption("🎯 InterviewMate | Streamlit + Ollama + Llama 3.2 + Whisper + Live Camera")
st.caption("🔒 AI processing is designed to run locally using Ollama.")
