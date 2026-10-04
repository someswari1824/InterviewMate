import os
import time
import html
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from pypdf import PdfReader

from ai import ask_ai
from speech import transcribe_audio
from question import (
    generate_question,
    evaluate_answer,
    extract_score
)

try:
    from streamlit_webrtc import WebRtcMode, webrtc_streamer
    from aiortc.contrib.media import MediaRecorder

    WEBRTC_AVAILABLE = True
except Exception:
    WEBRTC_AVAILABLE = False


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="InterviewMate",
    page_icon="🎯",
    layout="wide"
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .question-box {
        padding: 22px;
        border-radius: 15px;
        background-color: #1e293b;
        border-left: 6px solid #4b6cff;
        color: white;
        font-size: 20px;
        font-weight: 500;
        line-height: 1.6;
        margin-bottom: 15px;
    }

    .timer-box {
        padding: 12px;
        border-radius: 12px;
        border: 2px solid #ff4b4b;
        text-align: center;
        font-size: 25px;
        font-weight: bold;
        background-color: #1e293b;
        color: white;
    }

    .feedback-box {
        padding: 20px;
        border-radius: 15px;
        background-color: #1e293b;
        border-left: 6px solid #22c55e;
        color: white;
        font-size: 16px;
        line-height: 1.6;
        margin-top: 10px;
    }

    .answer-box {
        padding: 15px;
        border-radius: 12px;
        background-color: #0f172a;
        border: 1px solid #334155;
        color: white;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "candidate_name": "",
    "role": "",
    "interview_type": "Mixed Interview",

    "resume_text": "",
    "resume_topics": [],
    "selected_topics": [],

    "question_number": 0,
    "current_question": "",
    "previous_questions": [],

    "current_answer": "",
    "last_voice_answer": "",

    "feedback": "",

    "technical_scores": [],
    "clarity_scores": [],

    "question_history": [],

    "interview_started": False,
    "interview_finished": False,

    "interview_duration": 10 * 60,
    "interview_start_time": None,
    "interview_end_time": None,

    "camera_enabled": True,

    "last_spoken_question": "",

    "skipped_questions": 0,
}


for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# RESUME EXTRACTION
# ============================================================

def extract_resume_text(uploaded_file):

    if uploaded_file is None:
        return ""

    try:
        reader = PdfReader(uploaded_file)

        text = ""

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

        return text.strip()

    except Exception as e:
        st.error(f"Could not read resume: {e}")
        return ""


# ============================================================
# EXTRACT TOPICS FROM RESUME
# ============================================================

def extract_topics(resume_text):

    if not resume_text:
        return []

    prompt = f"""
You are analyzing a student's resume for a technical interview.

Resume:

{resume_text[:8000]}

Extract the important technical interview topics.

Return ONLY a comma-separated list.

Example:

Java, Python, SQL, DBMS, Operating Systems, Computer Networks, Docker

Do not explain anything.
"""

    try:

        response = ask_ai(prompt)

        topics = [
            topic.strip()
            for topic in response.split(",")
            if topic.strip()
        ]

        return topics

    except Exception as e:

        st.warning(f"Could not extract topics: {e}")

        return []


# ============================================================
# ASK NEXT QUESTION
# ============================================================

def ask_next_question():

    # VERY IMPORTANT:
    # Never generate a question if time is already finished.

    if remaining_seconds() <= 0:

        finish_interview()

        return False

    question = generate_question(
        candidate_name=st.session_state.candidate_name,
        role=st.session_state.role,
        interview_type=st.session_state.interview_type,
        topics=st.session_state.selected_topics,
        resume_text=st.session_state.resume_text,
        question_number=st.session_state.question_number,
        previous_questions=st.session_state.previous_questions
    )

    if not question:

        return False

    st.session_state.current_question = question

    st.session_state.previous_questions.append(question)

    st.session_state.last_spoken_question = ""

    return True


# ============================================================
# SPEAK QUESTION
# ============================================================

def speak_question(question):

    if not question:
        return

    safe_question = html.escape(question)

    components.html(
        f"""
        <script>

        const question = {safe_question!r};

        if ('speechSynthesis' in window) {{

            window.speechSynthesis.cancel();

            const speech = new SpeechSynthesisUtterance(question);

            speech.lang = "en-US";
            speech.rate = 0.9;
            speech.pitch = 1;

            window.speechSynthesis.speak(speech);
        }}

        </script>
        """,
        height=0
    )


# ============================================================
# TIMER
# ============================================================

def remaining_seconds():

    if not st.session_state.interview_started:
        return 0

    if st.session_state.interview_end_time is None:
        return 0

    remaining = int(
        st.session_state.interview_end_time - time.time()
    )

    return max(0, remaining)


def format_time(seconds):

    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes:02d}:{seconds:02d}"


# ============================================================
# FINISH INTERVIEW
# ============================================================

def finish_interview():

    st.session_state.interview_finished = True
    st.session_state.interview_started = False

    st.session_state.current_question = ""

    # Stop browser speech
    components.html(
        """
        <script>
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
        </script>
        """,
        height=0
    )


# ============================================================
# SCORE CALCULATION
# ============================================================

def calculate_average(scores):

    if not scores:
        return 0

    return round(sum(scores) / len(scores), 2)


# ============================================================
# CAMERA
# ============================================================

def show_live_camera():

    if not WEBRTC_AVAILABLE:

        st.warning(
            "Camera feature is unavailable. "
            "Install streamlit-webrtc and aiortc."
        )

        return

    recordings_dir = Path("recordings")

    recordings_dir.mkdir(exist_ok=True)

    recording_path = (
        recordings_dir / "interview_recording.webm"
    )

    def recorder_factory():

        return MediaRecorder(
            str(recording_path)
        )

    # IMPORTANT:
    # Camera = video only
    # Microphone = handled separately by st.audio_input()

    ctx = webrtc_streamer(
        key="interview-camera-recorder",

        mode=WebRtcMode.SENDRECV,

        media_stream_constraints={
            "video": True,
            "audio": False
        },

        in_recorder_factory=recorder_factory,

        rtc_configuration={
            "iceServers": [
                {
                    "urls": [
                        "stun:stun.l.google.com:19302"
                    ]
                }
            ]
        },

        media_toggle_controls=True
    )

    return ctx


# ============================================================
# TIMER PANEL
# ============================================================

@st.fragment(run_every="1s")
def timer_panel():

    if not st.session_state.interview_started:

        return

    seconds = remaining_seconds()

    if seconds <= 0:

        finish_interview()

        st.rerun()

        return

    st.markdown(
        f"""
        <div class="timer-box">
            ⏱ {format_time(seconds)}
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🎯 InterviewMate")

st.sidebar.markdown(
    "### Interview Settings"
)


# Candidate name

candidate_name = st.sidebar.text_input(
    "Candidate Name",
    value=st.session_state.candidate_name
)

st.session_state.candidate_name = candidate_name


# Target role

role = st.sidebar.selectbox(
    "Target Role",
    [
        "Software Developer",
        "Java Developer",
        "Python Developer",
        "Backend Developer",
        "Full Stack Developer",
        "Data Analyst",
        "Other"
    ]
)

st.session_state.role = role


# Interview type

interview_type = st.sidebar.selectbox(
    "Interview Type",
    [
        "Resume Based",
        "Core Subjects",
        "Mixed Interview",
        "Full Mock Interview"
    ]
)

st.session_state.interview_type = interview_type


# Duration

duration_minutes = st.sidebar.selectbox(
    "Interview Duration",
    [
        5,
        10,
        15,
        20,
        30
    ],
    index=1
)

st.session_state.interview_duration = (
    duration_minutes * 60
)


# Camera

camera_enabled = st.sidebar.checkbox(
    "Enable Camera",
    value=True
)

st.session_state.camera_enabled = camera_enabled


# ============================================================
# MAIN HEADER
# ============================================================

st.title("🎯 InterviewMate")

st.write(
    "AI-powered mock interview practice with "
    "resume-based questions, voice answers and feedback."
)


# ============================================================
# RESUME UPLOAD
# ============================================================

if not st.session_state.interview_started:

    st.subheader("📄 Upload Resume")

    uploaded_file = st.file_uploader(
        "Upload your resume PDF",
        type=["pdf"]
    )

    if uploaded_file is not None:

        resume_text = extract_resume_text(
            uploaded_file
        )

        if resume_text:

            st.session_state.resume_text = resume_text

            st.success(
                "Resume uploaded successfully."
            )

            # Extract topics only once
            if not st.session_state.resume_topics:

                with st.spinner(
                    "AI is analyzing your resume..."
                ):

                    topics = extract_topics(
                        resume_text
                    )

                    st.session_state.resume_topics = topics

            if st.session_state.resume_topics:

                st.subheader(
                    "🧠 Resume Topics"
                )

                selected_topics = st.multiselect(
                    "Select topics you want to practice",
                    st.session_state.resume_topics,
                    default=st.session_state.selected_topics
                )

                st.session_state.selected_topics = (
                    selected_topics
                )


# ============================================================
# START INTERVIEW
# ============================================================

if (
    not st.session_state.interview_started
    and not st.session_state.interview_finished
):

    st.markdown("---")

    if st.button(
        "🚀 Start Interview",
        type="primary",
        use_container_width=True
    ):

        if not st.session_state.candidate_name.strip():

            st.warning(
                "Please enter your name."
            )

        elif not st.session_state.resume_text.strip():

            st.warning(
                "Please upload your resume."
            )

        else:

            st.session_state.interview_started = True
            st.session_state.interview_finished = False

            st.session_state.question_number = 1

            st.session_state.previous_questions = []

            st.session_state.current_answer = ""

            st.session_state.last_voice_answer = ""

            st.session_state.feedback = ""

            st.session_state.technical_scores = []

            st.session_state.clarity_scores = []

            st.session_state.question_history = []

            st.session_state.skipped_questions = 0

            start_time = time.time()

            st.session_state.interview_start_time = start_time

            st.session_state.interview_end_time = (
                start_time +
                st.session_state.interview_duration
            )

            ask_next_question()

            st.rerun()


# ============================================================
# INTERVIEW FINISHED
# ============================================================

if st.session_state.interview_finished:

    st.success("🎉 Interview Completed!")

    st.markdown("---")

    st.header("📊 Final Interview Report")

    technical_average = calculate_average(
        st.session_state.technical_scores
    )

    clarity_average = calculate_average(
        st.session_state.clarity_scores
    )

    if technical_average or clarity_average:

        overall_score = round(
            (technical_average + clarity_average) / 2,
            2
        )

    else:

        overall_score = 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Technical Score",
            f"{technical_average}/10"
        )

    with col2:

        st.metric(
            "Clarity Score",
            f"{clarity_average}/10"
        )

    with col3:

        st.metric(
            "Overall Score",
            f"{overall_score}/10"
        )

    with col4:

        st.metric(
            "Questions Skipped",
            st.session_state.skipped_questions
        )

    st.markdown("---")

    st.subheader(
        f"📝 Questions Attempted: "
        f"{len(st.session_state.question_history)}"
    )

    for index, item in enumerate(
        st.session_state.question_history,
        start=1
    ):

        st.markdown(
            f"### Question {index}"
        )

        st.write(
            item.get("question", "")
        )

        if item.get("skipped"):

            st.info("⏭️ Question skipped.")

        else:

            st.write(
                "**Your Answer:**"
            )

            st.write(
                item.get("answer", "")
            )

            st.write(
                f"**Technical Score:** "
                f"{item.get('technical_score', 0)}/10"
            )

            st.write(
                f"**Clarity Score:** "
                f"{item.get('clarity_score', 0)}/10"
            )

            feedback = item.get(
                "feedback",
                ""
            )

            if feedback:

                st.markdown(
                    f"""
                    <div class="feedback-box">
                        <pre style="
                            white-space: pre-wrap;
                            color: white;
                            font-family: Arial, sans-serif;
                            font-size: 16px;
                            line-height: 1.6;
                        ">{html.escape(feedback)}</pre>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        st.markdown("---")

    if st.button(
        "🔄 Start New Interview",
        use_container_width=True
    ):

        for key in defaults:

            if key == "interview_duration":
                continue

            if key in st.session_state:

                del st.session_state[key]

        st.rerun()

    st.stop()


# ============================================================
# LIVE INTERVIEW
# ============================================================

if st.session_state.interview_started:

    # Check timer BEFORE displaying/generating question

    if remaining_seconds() <= 0:

        finish_interview()

        st.rerun()

    # --------------------------------------------------------
    # TWO COLUMN LAYOUT
    # --------------------------------------------------------

    left_column, right_column = st.columns(
        [2.2, 1]
    )


    # ========================================================
    # LEFT SIDE
    # ========================================================

    with left_column:

        st.subheader(
            f"Question {st.session_state.question_number}"
        )

        question = (
            st.session_state.current_question
        )

        st.markdown(
            f"""
            <div class="question-box">
                {html.escape(question)}
            </div>
            """,
            unsafe_allow_html=True
        )


        # Speak question button

        if st.button(
            "🔊 Speak Question Again"
        ):

            speak_question(
                question
            )


        # Automatically speak new question

        if (
            question
            and
            st.session_state.last_spoken_question
            != question
        ):

            speak_question(
                question
            )

            st.session_state.last_spoken_question = (
                question
            )


        st.markdown("### 🎤 Your Answer")


        # ====================================================
        # TEXT ANSWER
        # ====================================================

        typed_answer = st.text_area(
            "Type your answer",
            value=st.session_state.current_answer,
            height=150,
            key="typed_answer_box"
        )


        # ====================================================
        # VOICE ANSWER
        # ====================================================

        audio_value = st.audio_input(
            "🎤 Record your answer"
        )


        if audio_value is not None:

            try:

                audio_bytes = audio_value.getvalue()

                with st.spinner(
                    "Converting your speech to text..."
                ):

                    transcript = transcribe_audio(
                        audio_bytes
                    )

                if transcript:

                    st.session_state.last_voice_answer = (
                        transcript
                    )

                    st.success(
                        "Voice converted to text."
                    )

                    st.markdown(
                        "**🎤 Transcribed Answer:**"
                    )

                    st.info(
                        transcript
                    )

                else:

                    st.warning(
                        "Could not understand the audio. "
                        "Please try speaking clearly."
                    )

            except Exception as e:

                st.error(
                    f"Speech recognition error: {e}"
                )


        # ====================================================
        # FINAL ANSWER USED
        # ====================================================

        voice_answer = (
            st.session_state.last_voice_answer.strip()
        )

        typed_answer_clean = (
            typed_answer.strip()
        )

        if voice_answer:

            final_answer = voice_answer

        else:

            final_answer = typed_answer_clean


        # ====================================================
        # BUTTONS
        # ====================================================

        submit_column, skip_column = st.columns(2)


        # ====================================================
        # SUBMIT ANSWER
        # ====================================================

        with submit_column:

            if st.button(
                "✅ Submit Answer",
                type="primary",
                use_container_width=True
            ):

                # Check timer again before processing

                if remaining_seconds() <= 0:

                    finish_interview()

                    st.rerun()

                elif len(final_answer) < 5:

                    st.warning(
                        "Please provide an answer "
                        "or skip the question."
                    )

                else:

                    with st.spinner(
                        "AI is evaluating your answer..."
                    ):

                        feedback = evaluate_answer(
                            question,
                            final_answer
                        )

                    technical_score = extract_score(
                        feedback,
                        "SCORE"
                    )

                    clarity_score = extract_score(
                        feedback,
                        "CLARITY"
                    )

                    # Prevent zero caused by parser failure
                    if technical_score == 0:
                        technical_score = 1

                    if clarity_score == 0:
                        clarity_score = 1


                    # Save scores

                    st.session_state.technical_scores.append(
                        technical_score
                    )

                    st.session_state.clarity_scores.append(
                        clarity_score
                    )


                    # Save feedback

                    st.session_state.feedback = (
                        feedback
                    )


                    # Save history

                    st.session_state.question_history.append(
                        {
                            "question": question,
                            "answer": final_answer,
                            "feedback": feedback,
                            "technical_score": technical_score,
                            "clarity_score": clarity_score,
                            "skipped": False
                        }
                    )


                    # Clear answer

                    st.session_state.current_answer = ""

                    st.session_state.last_voice_answer = ""


                    # IMPORTANT:
                    # Check time BEFORE generating next question

                    if remaining_seconds() > 0:

                        st.session_state.question_number += 1

                        ask_next_question()

                        st.rerun()

                    else:

                        finish_interview()

                        st.rerun()


        # ====================================================
        # SKIP QUESTION
        # ====================================================

        with skip_column:

            if st.button(
                "⏭️ Skip Question",
                use_container_width=True
            ):

                # Check timer

                if remaining_seconds() <= 0:

                    finish_interview()

                    st.rerun()

                else:

                    # Save skipped question

                    st.session_state.question_history.append(
                        {
                            "question": question,
                            "answer": "",
                            "feedback": "",
                            "technical_score": 0,
                            "clarity_score": 0,
                            "skipped": True
                        }
                    )

                    st.session_state.skipped_questions += 1


                    # Clear previous answer

                    st.session_state.current_answer = ""

                    st.session_state.last_voice_answer = ""

                    st.session_state.feedback = ""


                    # Only ask next question if time remains

                    if remaining_seconds() > 0:

                        st.session_state.question_number += 1

                        ask_next_question()

                        st.rerun()

                    else:

                        finish_interview()

                        st.rerun()


    # ========================================================
    # RIGHT SIDE
    # ========================================================

    with right_column:

        st.subheader("⏱ Interview Time")

        timer_panel()

        st.markdown("---")


        # ====================================================
        # CAMERA
        # ====================================================

        if st.session_state.camera_enabled:

            st.subheader("📷 Live Camera")

            show_live_camera()

        else:

            st.info(
                "Camera is disabled."
            )


        # ====================================================
        # PREVIOUS EVALUATION
        # ====================================================

        if st.session_state.feedback:

            st.markdown("---")

            st.subheader(
                "📊 Previous Answer Evaluation"
            )

            safe_feedback = html.escape(
                st.session_state.feedback
            )

            st.markdown(
                f"""
                <div class="feedback-box">
                    <pre style="
                        white-space: pre-wrap;
                        color: white;
                        font-family: Arial, sans-serif;
                        font-size: 16px;
                        line-height: 1.6;
                    ">{safe_feedback}</pre>
                </div>
                """,
                unsafe_allow_html=True
            )