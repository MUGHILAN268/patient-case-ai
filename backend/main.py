import os
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from google import genai

try:
    from backend.database import create_table, get_connection
    from backend.models import (
        ChatReply,
        ChatRequest,
        GeminiChatRequest,
        GeminiSummaryRequest,
        Patient,
    )
except ModuleNotFoundError:
    from database import get_connection, create_table
    from models import (
        ChatReply,
        ChatRequest,
        GeminiChatRequest,
        GeminiSummaryRequest,
        Patient,
    )

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

api_key = os.getenv("GEMINI_API_KEY", "").strip()
client = genai.Client(api_key=api_key) if api_key and api_key != "YOUR_GEMINI_API_KEY" else None
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

app = FastAPI(
    title="CareAI Patient Case Taking API",
    description="Backend for AI powered patient case taking using Gemini",
    version="1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

create_table()
conversation_state: Dict[int, str] = {}


@app.get("/")
def home():
    return {
        "message": "CareAI Backend + Gemini is running",
        "gemini_configured": client is not None,
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "gemini_configured": client is not None,
        "model": GEMINI_MODEL,
    }


@app.post("/patients")
def create_patient(patient: Patient):
    summary = generate_summary(patient)

    connection = get_connection()
    cursor = connection.execute(
        """
        INSERT INTO patients
        (
            name,
            abha_id,
            age,
            gender,
            complaint,
            history,
            symptoms,
            medications,
            allergies,
            medical_history,
            summary
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            patient.name,
            patient.abha_id,
            patient.age,
            patient.gender,
            patient.complaint,
            patient.history,
            patient.symptoms,
            patient.medications,
            patient.allergies,
            patient.medical_history,
            summary,
        ),
    )
    connection.commit()
    patient_id = cursor.lastrowid
    connection.close()

    conversation_state[patient_id] = "initial"

    return {
        "message": "Patient case saved successfully",
        "patient_id": patient_id,
        "summary": summary,
    }


@app.get("/patients")
def get_patients():
    connection = get_connection()
    patients = connection.execute("SELECT * FROM patients ORDER BY id DESC").fetchall()
    connection.close()
    return [dict(patient) for patient in patients]


@app.get("/patients/{patient_id}")
def get_patient(patient_id: int):
    connection = get_connection()
    patient = connection.execute(
        "SELECT * FROM patients WHERE id = ?",
        (patient_id,),
    ).fetchone()
    connection.close()

    if patient is None:
        return {"error": "Patient not found"}

    return dict(patient)


@app.post("/chat")
def chat(request: GeminiChatRequest):
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini is not configured. Add a valid GEMINI_API_KEY to backend/.env.",
        )

    conversation_text = ""

    for item in request.conversation:
        role = item.get("role", "user")
        message = item.get("message", "")
        conversation_text += f"{role}: {message}\n"

    prompt = f"""
You are CareAI, an AI-assisted patient case-taking and documentation assistant.

Your job is to ask one relevant question at a time to collect information for a doctor.

Rules:
1. Ask only ONE question at a time.
2. Use simple language.
3. Do not diagnose the patient.
4. Do not prescribe medicines.
5. Do not claim to replace a doctor.
6. If the patient reports something potentially urgent, tell them that prompt medical evaluation may be needed.
7. Keep responses short.

Previous conversation:

{conversation_text}

Patient's latest answer:

{request.message}

Respond with the next appropriate question.
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        reply = (response.text or "").strip()
        if not reply:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemini returned an empty response.",
            )
        return {"reply": reply}
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API request failed: {exc}",
        ) from exc


@app.post("/summary")
def generate_summary_endpoint(request: GeminiSummaryRequest):
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini is not configured. Add a valid GEMINI_API_KEY to backend/.env.",
        )

    conversation_text = ""

    for item in request.conversation:
        role = item.get("role", "")
        message = item.get("message", "")
        conversation_text += f"{role}: {message}\n"

    prompt = f"""
You are a medical documentation assistant.

Create a concise, structured patient case summary from the conversation below.

Use these sections:
1. Chief Complaint
2. History of Present Illness
3. Associated Symptoms
4. Past Medical History
5. Medications
6. Allergies
7. Other Relevant Information
8. Important Notes

Only include information actually provided by the patient.
Do not invent information.
Do not provide a diagnosis.
End with: "Doctor review required for clinical assessment."

Conversation:

{conversation_text}
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        summary = (response.text or "").strip()
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemini returned an empty summary.",
            )
        return {"summary": summary}
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Summary generation failed: {exc}",
        ) from exc


@app.post("/chat-legacy", response_model=ChatReply)
def chat_with_patient(payload: ChatRequest):
    connection = get_connection()
    patient = connection.execute(
        "SELECT * FROM patients WHERE id = ?",
        (payload.patient_id,),
    ).fetchone()
    connection.close()

    if patient is None:
        return ChatReply(reply="Patient not found. Please register the patient first.")

    text = payload.message.strip().lower()
    state = conversation_state.get(payload.patient_id, "initial")

    if state == "initial":
        conversation_state[payload.patient_id] = "asked_location"
        return ChatReply(reply="Where exactly is the pain or discomfort located?")

    if state == "asked_location":
        conversation_state[payload.patient_id] = "asked_pattern"
        return ChatReply(reply="Is the pain constant or does it come and go?")

    if state == "asked_pattern":
        conversation_state[payload.patient_id] = "asked_symptoms"
        return ChatReply(reply="Any fever, nausea, vomiting, or urinary symptoms?")

    if state == "asked_symptoms":
        conversation_state[payload.patient_id] = "asked_medications"
        return ChatReply(reply="Are there any current medications or recent treatment changes?")

    if state == "asked_medications":
        conversation_state[payload.patient_id] = "done"
        return ChatReply(reply="Any known allergies or past medical conditions we should document?")

    return ChatReply(reply="Thank you. The clinician will review the recorded case details.")


def generate_summary(patient: Patient):
    summary = f"""
PATIENT CASE SUMMARY

Patient Name: {patient.name}
ABHA ID: {patient.abha_id}
Age: {patient.age}
Gender: {patient.gender}

Chief Complaint:
{patient.complaint}

History of Present Illness:
{patient.history}

Associated Symptoms:
{patient.symptoms}

Medications:
{patient.medications}

Allergies:
{patient.allergies}

Past Medical History:
{patient.medical_history}

IMPORTANT:
This summary is generated from patient-provided information.
It is intended to assist the doctor with case documentation
and does not provide a diagnosis.
"""
    return summary
