import math

def calculate_bkt_step(p_l: float, is_correct: bool, p_g: float = 0.25, p_s: float = 0.10, p_t: float = 0.15) -> float:
    if is_correct:
        num = p_l * (1.0 - p_s)
        den = num + (1.0 - p_l) * p_g
    else:
        num = p_l * p_s
        den = num + (1.0 - p_l) * (1.0 - p_g)
    
    p_posterior = num / den if den > 0 else p_l
    p_next = p_posterior + (1.0 - p_posterior) * p_t
    return round(min(max(p_next, 0.01), 0.99), 4)

def calculate_stability(p_l: float, streak: int) -> float:
    base_stability = 60.0
    return round(base_stability * (1.0 + 0.5 * streak) * math.exp(2.0 * p_l), 2)

def calculate_retrievability(stability: float, elapsed_minutes: float) -> float:
    if stability <= 0:
        return 0.0
    return round(math.exp(-elapsed_minutes / stability), 4)

def predict_forget_minute(stability: float, threshold: float = 0.50) -> int:
    delta_min = -stability * math.log(threshold)
    return int(round(delta_min))
