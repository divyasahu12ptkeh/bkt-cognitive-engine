import random
from datetime import datetime, timedelta
from math_stubs import calculate_bkt_step, calculate_stability, predict_forget_minute

def run_simulation(student_id: str, concept_id: str, count: int, true_competence: float):
    results = []
    p_l = 0.10
    streak = 0
    clock = datetime.now()

    for i in range(count):
        is_correct = random.random() < true_competence
        streak = streak + 1 if is_correct else 0
        p_l = calculate_bkt_step(p_l, is_correct)
        stability = calculate_stability(p_l, streak)
        delta_min = predict_forget_minute(stability)
        
        clock += timedelta(minutes=random.randint(2, 8))
        forget_time = clock + timedelta(minutes=delta_min)
        
        results.append({
            "step": i + 1,
            "timestamp": clock.isoformat(),
            "is_correct": is_correct,
            "mastery_probability": p_l,
            "stability_minutes": stability,
            "predicted_forget_minute": forget_time.isoformat(),
            "minutes_until_review": delta_min
        })

    return results
