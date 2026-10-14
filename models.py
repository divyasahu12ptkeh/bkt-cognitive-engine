from pydantic import BaseModel, Field
from datetime import datetime

class AttemptRequest(BaseModel):
    student_id: str = "student_1"
    concept_id: str = "bayes_theorem"
    is_correct: bool
    response_time_ms: int = Field(default=3000, description="Latency in ms")

class StateResponse(BaseModel):
    student_id: str
    concept_id: str
    mastery_probability: float
    current_retrievability: float
    memory_stability_minutes: float
    predicted_forget_minute: datetime
    minutes_until_review: int
    last_updated: datetime

class TimeTravelRequest(BaseModel):
    student_id: str
    concept_id: str
    advance_minutes: int

class StreamSimulationRequest(BaseModel):
    student_id: str
    concept_id: str
    total_questions: int = 10
    true_student_mastery: float = Field(default=0.75, ge=0.0, le=1.0)