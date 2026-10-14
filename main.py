from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta

from models import AttemptRequest, StateResponse, TimeTravelRequest, StreamSimulationRequest
from state import state_manager
from math_stubs import calculate_bkt_step, calculate_stability, calculate_retrievability, predict_forget_minute
from simulator import run_simulation

app = FastAPI(title="Cognitive Engine API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/attempt", response_model=StateResponse)
def submit_attempt(req: AttemptRequest):
    state = state_manager.get_or_create(req.student_id, req.concept_id)
    
    streak = state["streak"] + 1 if req.is_correct else 0
    new_p_l = calculate_bkt_step(state["p_l"], req.is_correct)
    new_stability = calculate_stability(new_p_l, streak)
    minutes_to_forget = predict_forget_minute(new_stability)
    now = datetime.now()
    forget_timestamp = now + timedelta(minutes=minutes_to_forget)
    
    state_manager.update_state(req.student_id, req.concept_id, {
        "p_l": new_p_l,
        "stability": new_stability,
        "streak": streak,
        "last_updated": now,
        "virtual_time_offset_min": 0
    })
    
    return StateResponse(
        student_id=req.student_id,
        concept_id=req.concept_id,
        mastery_probability=new_p_l,
        current_retrievability=1.0,
        memory_stability_minutes=new_stability,
        predicted_forget_minute=forget_timestamp,
        minutes_until_review=minutes_to_forget,
        last_updated=now
    )

@app.get("/api/state", response_model=StateResponse)
def get_state(student_id: str = "student_1", concept_id: str = "bayes_theorem"):
    state = state_manager.get_or_create(student_id, concept_id)
    now = datetime.now()
    
    elapsed = (now - state["last_updated"]).total_seconds() / 60.0 + state["virtual_time_offset_min"]
    retrievability = calculate_retrievability(state["stability"], elapsed)
    minutes_to_forget = predict_forget_minute(state["stability"])
    forget_timestamp = state["last_updated"] + timedelta(minutes=minutes_to_forget)
    remaining_min = max(0, int(minutes_to_forget - elapsed))
    
    return StateResponse(
        student_id=student_id,
        concept_id=concept_id,
        mastery_probability=state["p_l"],
        current_retrievability=retrievability,
        memory_stability_minutes=state["stability"],
        predicted_forget_minute=forget_timestamp,
        minutes_until_review=remaining_min,
        last_updated=state["last_updated"]
    )

@app.post("/api/time-travel", response_model=StateResponse)
def time_travel(req: TimeTravelRequest):
    state = state_manager.get_or_create(req.student_id, req.concept_id)
    state["virtual_time_offset_min"] += req.advance_minutes
    return get_state(req.student_id, req.concept_id)

@app.post("/api/simulate-stream")
def simulate_stream(req: StreamSimulationRequest):
    return {
        "student_id": req.student_id,
        "concept_id": req.concept_id,
        "stream": run_simulation(req.student_id, req.concept_id, req.total_questions, req.true_student_mastery)
    }
from fastapi import Response

QUESTIONS_DB = [
    {
        "id": "q1",
        "concept_id": "bayes_theorem",
        "prompt": "What does P(A|B) represent in Bayes' Theorem?",
        "options": [
            "Probability of A given B has occurred",
            "Probability of B given A has occurred",
            "Joint probability of A and B",
            "Prior probability of A"
        ],
        "correct_index": 0
    },
    {
        "id": "q2",
        "concept_id": "bayes_theorem",
        "prompt": "If a student truly knows a topic, making an error is modeled by which parameter?",
        "options": ["Guess (P_G)", "Slip (P_S)", "Transition (P_T)", "Prior (P_L0)"],
        "correct_index": 1
    }
]

@app.get("/api/questions")
def get_questions(concept_id: str = "bayes_theorem"):
    return [q for q in QUESTIONS_DB if q["concept_id"] == concept_id]

@app.get("/api/schedule/export.ics")
def export_calendar(student_id: str = "student_1", concept_id: str = "bayes_theorem"):
    state = state_manager.get_or_create(student_id, concept_id)
    forget_time = state["last_updated"] + timedelta(minutes=state["stability"])
    start_str = forget_time.strftime("%Y%m%dT%H%M%SZ")
    end_str = (forget_time + timedelta(minutes=5)).strftime("%Y%m%dT%H%M%SZ")
    
    ics_body = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//CognitiveEngine//EN
BEGIN:VEVENT
SUMMARY:Review Session: {concept_id.replace('_', ' ').title()}
DESCRIPTION:Calculated memory threshold reached. Review now to reset retention curve.
DTSTART:{start_str}
DTEND:{end_str}
END:VEVENT
END:VCALENDAR"""
    return Response(
        content=ics_body,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=review_{concept_id}.ics"}
    )