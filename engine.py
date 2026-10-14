"""Cognitive engine: Bayesian Knowledge Tracing + Ebbinghaus forgetting curve.
All times are in MINUTES on a (possibly simulated) clock."""
import math
from dataclasses import dataclass, field


@dataclass
class BKTParams:
    p_init: float = 0.20      # P(L0): already knew the concept
    p_transit: float = 0.15   # P(T): learns from one practice
    p_slip: float = 0.10      # P(S): knows it but answers wrong
    p_guess: float = 0.25     # P(G): doesn't know but answers right
    stab_gain: float = 1.8    # memory strength x this after a correct answer
    stab_loss: float = 0.7    # memory strength x this after a wrong answer


@dataclass
class Concept:
    name: str
    p_known: float            # BKT mastery just after the last practice
    stability: float = 60.0   # S in R = exp(-t/S); minutes
    last_t: float = 0.0
    history: list = field(default_factory=list)  # (t, mastery, event, stability)
    last_trace: dict = field(default_factory=dict)  # numbers of the last update

    def __post_init__(self):
        if not self.history:
            self.history.append((self.last_t, self.p_known, "start", self.stability))


def retention(c: Concept, t: float) -> float:
    """Ebbinghaus: R(t) = exp(-(t - last_practice) / stability)."""
    return math.exp(-max(t - c.last_t, 0.0) / c.stability)


def mastery_at(c: Concept, t: float) -> float:
    """Effective mastery = BKT mastery x retention."""
    return c.p_known * retention(c, t)


def update(c: Concept, correct: bool, t: float, p: BKTParams) -> float:
    """Update concept state after an answer at time t. Returns new mastery."""
    dt = max(t - c.last_t, 0.0)
    R = retention(c, t)
    p_before, S_old = c.p_known, c.stability
    prior = p_before * R                          # forgetting lowers the prior
    if correct:
        num = prior * (1 - p.p_slip)
        den = num + (1 - prior) * p.p_guess
    else:
        num = prior * p.p_slip
        den = num + (1 - prior) * (1 - p.p_guess)
    post = num / den
    c.p_known = post + (1 - post) * p.p_transit  # chance of learning this step
    # spacing effect: a successful recall strengthens memory, a miss weakens it
    if correct:
        c.stability = min(S_old * p.stab_gain, 60 * 24 * 30)
    else:
        c.stability = max(S_old * p.stab_loss, 10)
    c.last_t = t
    c.history.append((t, c.p_known, "correct" if correct else "wrong", c.stability))
    c.last_trace = dict(
        t=t, dt=dt, R=R, S_old=S_old, S_new=c.stability, p_before=p_before,
        prior=prior, correct=correct, num=num, den=den, post=post,
        p_new=c.p_known, slip=p.p_slip, guess=p.p_guess, transit=p.p_transit,
        gain=p.stab_gain, loss=p.stab_loss,
    )
    return c.p_known


def time_to_threshold(c: Concept, threshold: float):
    """Minute at which effective mastery drops to `threshold` (None if already below)."""
    if c.p_known <= threshold:
        return None
    return c.last_t + c.stability * math.log(c.p_known / threshold)


def mastery_curve(c: Concept, t_end: float, per_seg: int = 25, last_seg: int = 100):
    """Full mastery-vs-time curve (past + future), with a jump at every answer."""
    xs, ys = [], []
    h = c.history
    for i, (t0, p0, _, S) in enumerate(h):
        is_last = i + 1 == len(h)
        t1 = max(t_end, t0) if is_last else h[i + 1][0]
        n = last_seg if is_last else per_seg
        for k in range(n + 1):
            x = t0 + (t1 - t0) * (k / n) ** 2      # denser right after each answer
            xs.append(x)
            ys.append(p0 * math.exp(-(x - t0) / S))
    return xs, ys
