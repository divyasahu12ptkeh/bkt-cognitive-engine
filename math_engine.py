import math

class BKTEngine:
    def __init__(self, p_init=0.1, p_transit=0.15, p_slip=0.1, p_guess=0.2, s_base=60.0):
        self.p_init = p_init
        self.p_transit = p_transit
        self.p_slip = p_slip
        self.p_guess = p_guess
        self.s_base = s_base

    def update_mastery(self, p_l: float, correct: bool) -> float:
        """Bayesian update + transition step."""
        if correct:
            numerator = p_l * (1.0 - self.p_slip)
            denominator = numerator + (1.0 - p_l) * self.p_guess
        else:
            numerator = p_l * self.p_slip
            denominator = numerator + (1.0 - p_l) * (1.0 - self.p_guess)

        p_posterior = numerator / max(denominator, 1e-9)
        p_l_next = p_posterior + (1.0 - p_posterior) * self.p_transit
        return min(max(p_l_next, 0.001), 0.999)

    def calculate_stability(self, p_l: float, streak: int) -> float:
        """Map mastery and streak to memory stability (minutes)."""
        return self.s_base * (1.0 + 2.0 * p_l) * (1.5 ** streak)

    def retrievability(self, delta_minutes: float, stability: float) -> float:
        """Ebbinghaus decay curve: R(t) = exp(-t / S)."""
        return math.exp(-delta_minutes / max(stability, 1e-5))

    def time_to_forget(self, stability: float, r_threshold: float = 0.70) -> float:
        """Exact minute solver: t_forget = -S * ln(R_threshold)."""
        return -stability * math.log(r_threshold)