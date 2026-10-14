import copy
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine import BKTParams, Concept, mastery_at, mastery_curve, time_to_threshold, update

DEFAULT_BANK = {
    "Binary Search": [
        ("Time complexity of binary search on a sorted array?", ["O(n)", "O(log n)", "O(n log n)", "O(1)"], 1),
        ("Binary search requires the array to be...", ["Sorted", "Unique", "Even-sized", "Linked"], 0),
        ("low=0, high=9: mid = (low+high)//2 equals?", ["3", "5", "4", "9"], 2),
        ("If target < arr[mid], search next in the...", ["Right half", "Left half", "Whole array", "Stop"], 1),
    ],
    "Stacks": [
        ("A stack follows which order?", ["FIFO", "LIFO", "Random", "Priority"], 1),
        ("Which structure manages function calls?", ["Queue", "Heap", "Stack", "Graph"], 2),
        ("Popping from an empty stack is called?", ["Overflow", "Underflow", "Deadlock", "Null"], 1),
        ("Best structure to check balanced parentheses?", ["Queue", "Stack", "Array only", "Tree"], 1),
    ],
    "Recursion": [
        ("Every recursive function needs a...", ["Loop", "Base case", "Global", "Pointer"], 1),
        ("No base case usually causes?", ["Stack overflow", "Faster code", "Underflow", "Nothing"], 0),
        ("fact(n)=n*fact(n-1), fact(0)=1. fact(5)?", ["25", "60", "120", "720"], 2),
        ("Naive recursive Fibonacci time complexity?", ["O(n)", "O(log n)", "O(n^2)", "O(2^n)"], 3),
    ],
}
PALETTE = ["#1e3a8a", "#0f766e", "#b45309", "#6d28d9", "#334155", "#9f1239"]
T_FORGET, T_REVIEW, P_INIT = 0.5, 0.7, 0.20
PROGRESS = Path(__file__).with_name("progress.json")   # saved between runs
QFILE = Path(__file__).with_name("questions.json")     # questions you add in the app
DEMO = [("Binary Search", [True, True, False, True, True]), ("Stacks", [True, False, True])]


def load_bank():
    bank = {k: list(v) for k, v in DEFAULT_BANK.items()}
    try:
        custom = json.loads(QFILE.read_text())
    except Exception:
        custom = {}
    for concept, items in custom.items():
        for it in items:
            bank.setdefault(concept, []).append((it["q"], it["options"], it["answer"]))
    return bank


def save_custom_question(concept, q, options, answer):
    try:
        data = json.loads(QFILE.read_text())
    except Exception:
        data = {}
    data.setdefault(concept, []).append({"q": q, "options": options, "answer": answer})
    QFILE.write_text(json.dumps(data, indent=2))


def answers_to_goal(c, t, p, goal=0.9, cap=15):
    """How many correct answers in a row (1 min apart) until mastery >= goal."""
    k, tt = copy.deepcopy(c), t
    for n in range(1, cap + 1):
        tt += 1
        update(k, True, tt, p)
        if k.p_known >= goal:
            return n
    return None


# ---------- saved stats (days visited, questions solved) ----------
def load_stats():
    try:
        d = json.loads(PROGRESS.read_text())
    except Exception:
        d = {}
    d.setdefault("visit_dates", [])
    d.setdefault("attempted", {})
    d.setdefault("correct", {})
    return d


def save_stats(d):
    try:
        PROGRESS.write_text(json.dumps(d, indent=2))
    except Exception:
        pass


def streak(dates):
    days, cur, n = {date.fromisoformat(x) for x in dates}, date.today(), 0
    while cur in days:
        n, cur = n + 1, cur - timedelta(days=1)
    return n


def fmt_dur(m):
    m = int(round(m))
    if m < 60:
        return f"{m} min"
    if m < 1440:
        return f"{m // 60} h {m % 60} min"
    return f"{m // 1440} d {(m % 1440) // 60} h"


st.set_page_config(page_title="Cognitive State Engine", layout="wide")
S = st.session_state

st.markdown("""
<style>
.stApp { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; }
[data-testid="stToolbar"], [data-testid="stDecoration"], footer { display: none !important; }
.block-container { padding-top: 2rem; max-width: 1280px; }
h1, h2, h3, h4 { color: #0f172a; letter-spacing: -0.01em; }
div[data-testid="stMetric"] { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 16px; }
div[data-testid="stMetricLabel"] p { color: #475569; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #e2e8f0; }
.stTabs [data-baseweb="tab"] { padding: 10px 18px; font-weight: 600; }
button[kind="primary"] { background-color: #1e3a8a; border-color: #1e3a8a; }
.chip { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.74rem; font-weight: 600; }
.chip-green { background: #dcfce7; color: #166534; }
.chip-amber { background: #fef3c7; color: #92400e; }
.chip-red { background: #fee2e2; color: #991b1b; }
.chip-grey { background: #e2e8f0; color: #475569; }
</style>
""", unsafe_allow_html=True)

# ---------- sidebar: model parameters ----------
with st.sidebar:
    st.subheader("Model parameters")
    st.caption("Adjust a value and every calculation and curve updates immediately.")
    p_slip = st.slider("Slip probability (knows it, answers wrong)", 0.01, 0.40, 0.10, 0.01)
    p_guess = st.slider("Guess probability (does not know, answers right)", 0.01, 0.50, 0.25, 0.01)
    p_transit = st.slider("Learning rate per attempt", 0.01, 0.50, 0.15, 0.01)
    gain = st.slider("Memory strength multiplier, correct answer", 1.0, 3.0, 1.8, 0.1)
    loss = st.slider("Memory strength multiplier, wrong answer", 0.3, 1.0, 0.7, 0.05)
    P = BKTParams(P_INIT, p_transit, p_slip, p_guess, gain, loss)
    st.divider()
    st.subheader("Session")
    demo = st.button("Load sample scenario", width="stretch",
                     help="Fills the charts with simulated answers. Not counted in your statistics.")
    restart = st.button("Restart session", width="stretch", help="Keeps saved statistics.")
    wipe = st.button("Reset saved statistics", width="stretch")

if restart:
    for k in list(S.keys()):
        del S[k]
    st.rerun()

if "init" not in S:
    bank = load_bank()
    S.update(init=True, t=0.0, start=datetime.now(), msg=None, flash=None, bank=bank,
             concepts={n: Concept(n, P_INIT) for n in bank}, idx={n: 0 for n in bank},
             stats=load_stats())
    today = date.today().isoformat()
    if today not in S.stats["visit_dates"]:
        S.stats["visit_dates"].append(today)
        save_stats(S.stats)
if wipe:
    S.stats = {"visit_dates": [date.today().isoformat()], "attempted": {}, "correct": {}}
    save_stats(S.stats)
if demo:
    for n, seq in DEMO:
        if n in S.concepts:
            for ok in seq:
                S.t += 1
                update(S.concepts[n], ok, S.t, P)
            S.t += 45
    S.msg = None
    st.rerun()

dtm = lambda m: S.start + timedelta(minutes=m)
clock = lambda m: dtm(m).strftime("%d %b, %I:%M %p")
color = lambda n: PALETTE[list(S.bank).index(n) % len(PALETTE)]
chip = lambda text, tone: f"<span class='chip chip-{tone}'>{text}</span>"


def status(mv):
    if mv >= T_REVIEW:
        return "Strong", "green"
    if mv >= T_FORGET:
        return "Fading", "amber"
    return "Below threshold", "red"


# ---------- header + summary cards ----------
st.markdown("""
<div style="border-bottom: 3px solid #1e3a8a; padding-bottom: 12px; margin-bottom: 20px;">
  <div style="font-size: 0.78rem; letter-spacing: 0.14em; color: #64748b; text-transform: uppercase;">Learning analytics</div>
  <div style="font-size: 1.9rem; font-weight: 700; color: #0f172a;">Cognitive State Engine</div>
  <div style="color: #475569;">Bayesian Knowledge Tracing with the Ebbinghaus forgetting curve</div>
</div>
""", unsafe_allow_html=True)

att, cor = sum(S.stats["attempted"].values()), sum(S.stats["correct"].values())
mastered = sum(mastery_at(k, S.t) >= T_REVIEW for k in S.concepts.values())
days, strk = len(set(S.stats["visit_dates"])), streak(S.stats["visit_dates"])
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Days active", days, delta=f"Current streak: {strk} day(s)", delta_color="off")
c2.metric("Questions solved", cor, delta=f"{att} attempted", delta_color="off")
c3.metric("Accuracy", f"{cor / att:.0%}" if att else "n/a")
c4.metric("Concepts mastered", f"{mastered} of {len(S.bank)}", delta="Mastery of 70% or more", delta_color="off")
c5.metric("Session clock", dtm(S.t).strftime("%I:%M %p"), delta=dtm(S.t).strftime("%d %b %Y"), delta_color="off")
st.write("")

tab_practice, tab_plan, tab_curves, tab_math, tab_progress, tab_add = st.tabs(
    ["Practice", "Study plan", "Memory curves", "Method", "Progress", "Question bank"])

# ---------- Practice ----------
with tab_practice:
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        mode = st.radio("Mode", ["Select a concept", "Adaptive (weakest concept first)"], horizontal=True)
        if mode.startswith("Adaptive"):
            name = min(S.bank, key=lambda n: mastery_at(S.concepts[n], S.t))
            st.info(f"Adaptive mode selected **{name}**, where current mastery is lowest "
                    f"({mastery_at(S.concepts[name], S.t):.0%}).")
        else:
            name = st.selectbox("Concept", list(S.bank))
        c = S.concepts[name]
        q, opts, ans = S.bank[name][S.idx[name] % len(S.bank[name])]
        st.markdown(f"**Question {S.stats['attempted'].get(name, 0) + 1}.** {q}")
        choice = st.radio("Options", opts, index=None, key=f"{name}-{S.idx[name]}",
                          label_visibility="collapsed")
        if st.button("Submit answer", type="primary", disabled=choice is None):
            ok = opts.index(choice) == ans
            S.t += 1
            before = mastery_at(c, S.t)
            update(c, ok, S.t, P)
            S.idx[name] += 1
            S.stats["attempted"][name] = S.stats["attempted"].get(name, 0) + 1
            if ok:
                S.stats["correct"][name] = S.stats["correct"].get(name, 0) + 1
            save_stats(S.stats)
            S.msg = dict(ok=ok, name=name, ans=opts[ans], before=before, after=c.p_known)
            st.rerun()
        m = S.msg
        if m:
            text = f"{m['name']}: mastery changed from {m['before']:.0%} to {m['after']:.0%}."
            (st.success if m["ok"] else st.error)(
                ("Correct. " if m["ok"] else f"Incorrect. The right answer is {m['ans']}. ") + text)
        st.markdown("**Advance simulated time**")
        st.caption("Moves the session clock forward so memory decay can be observed without waiting.")
        b1, b2, b3 = st.columns(3)
        for col, label, mins in ((b1, "+30 minutes", 30), (b2, "+6 hours", 360), (b3, "+1 day", 1440)):
            if col.button(label, width="stretch"):
                S.t += mins
                S.msg = None
                st.rerun()
    with right:
        st.markdown("**Current mastery by concept**")
        for n, k in S.concepts.items():
            mv = mastery_at(k, S.t)
            label, tone = status(mv)
            st.markdown(f"**{n}** &nbsp; {chip(label, tone)} &nbsp; {mv:.0%}", unsafe_allow_html=True)
            st.progress(min(max(mv, 0.0), 1.0))
        st.caption("Strong: 70% and above. Fading: 50% to 70%. Below threshold: under 50%.")

# ---------- Study plan ----------
with tab_plan:
    st.markdown("### Recommended revision order")
    plan = [(mastery_at(k, S.t), n, k, time_to_threshold(k, T_REVIEW), answers_to_goal(k, S.t, P))
            for n, k in S.concepts.items()]
    plan.sort(key=lambda x: x[0])
    if plan[0][0] < T_REVIEW:
        st.success(f"Start with **{plan[0][1]}**. Current mastery is {plan[0][0]:.0%}.")
    else:
        nxt = min(plan, key=lambda x: x[3])
        st.success(f"All concepts are at 70% or above. Next review: **{nxt[1]}**, before {clock(nxt[3])}.")
    st.caption("Concepts are ranked by current mastery, the model's estimate of what is remembered right now.")
    for rank, (mv, n, k, tr, need) in enumerate(plan, 1):
        with st.container(border=True):
            a, b, c_ = st.columns([1.2, 2, 1.6])
            a.markdown(f"**{rank}. {n}**")
            a.caption(f"Memory strength: {fmt_dur(k.stability)}")
            b.progress(min(max(mv, 0.0), 1.0), text=f"Current mastery: {mv:.0%}")
            if tr is None or tr <= S.t:
                b.markdown(chip("Revise now", "red"), unsafe_allow_html=True)
            else:
                b.markdown(f"{chip('Scheduled', 'amber')} &nbsp; Revise before {clock(tr)}", unsafe_allow_html=True)
            c_.metric("Correct answers to reach 90%", f"{need}" if need else "More than 15")
    st.caption("Select Adaptive mode in the Practice tab to follow this order automatically.")

# ---------- Memory curves ----------
with tab_curves:
    a, b = st.columns([3, 1])
    chosen = a.multiselect("Concepts", list(S.bank), default=list(S.bank))
    window = b.selectbox("Time window", ["Next 6 hours", "Next 24 hours", "Next 3 days", "Next 7 days"], index=1)
    span = {"Next 6 hours": 360, "Next 24 hours": 1440, "Next 3 days": 4320, "Next 7 days": 10080}[window]
    x0, x1 = max(S.t - 0.2 * span, 0), S.t + span

    fig = go.Figure()
    fig.add_hrect(y0=0, y1=50, fillcolor="#ef4444", opacity=0.06, line_width=0)
    fig.add_hrect(y0=70, y1=100, fillcolor="#22c55e", opacity=0.06, line_width=0)
    for y, txt in ((25, "Below threshold (under 50%)"), (85, "Strong (70% and above)")):
        fig.add_annotation(xref="paper", x=0.995, y=y, text=txt, showarrow=False,
                           xanchor="right", font=dict(size=11, color="#64748b"))
    for n in chosen:
        k, col = S.concepts[n], color(n)
        xs, ys = mastery_curve(k, x1)
        fig.add_trace(go.Scatter(
            x=[dtm(x) for x in xs], y=[v * 100 for v in ys], mode="lines", name=n,
            line=dict(color=col, width=2.5),
            hovertemplate=f"<b>{n}</b><br>%{{x|%d %b, %I:%M %p}}<br>Mastery: %{{y:.0f}}%<extra></extra>"))
        ev = k.history[1:]
        if ev:
            fig.add_trace(go.Scatter(
                x=[dtm(e[0]) for e in ev], y=[e[1] * 100 for e in ev], mode="markers", showlegend=False,
                marker=dict(size=10, color=col, line=dict(color="white", width=1.5),
                            symbol=["circle" if e[2] == "correct" else "x" for e in ev]),
                text=[f"Answered {e[2]}" for e in ev],
                hovertemplate=f"<b>{n}</b><br>%{{text}}<br>Mastery after: %{{y:.0f}}%<extra></extra>"))
        tf = time_to_threshold(k, T_FORGET)
        if tf and x0 <= tf <= x1:
            fig.add_trace(go.Scatter(
                x=[dtm(tf)], y=[50], mode="markers", showlegend=False,
                marker=dict(size=13, color=col, symbol="diamond", line=dict(color="white", width=2)),
                hovertemplate=f"<b>{n}</b><br>Mastery falls to 50% at {clock(tf)}<extra></extra>"))
    fig.add_shape(type="line", x0=dtm(S.t), x1=dtm(S.t), y0=0, y1=100,
                  line=dict(color="#475569", width=1.5, dash="dot"))
    fig.add_annotation(x=dtm(S.t), y=104, text="Current time", showarrow=False, font=dict(size=11, color="#475569"))
    fig.update_layout(
        template="plotly_white", height=460, margin=dict(l=10, r=10, t=30, b=10), hovermode="closest",
        legend=dict(orientation="h", y=1.08, x=0),
        xaxis=dict(range=[dtm(x0), dtm(x1)], nticks=6, tickformat="%I:%M %p<br>%d %b", showgrid=False),
        yaxis=dict(range=[0, 108], tickvals=[0, 25, 50, 75, 100], ticksuffix="%",
                   title="Estimated retention", gridcolor="rgba(148,163,184,0.25)"))
    st.plotly_chart(fig, width="stretch")
    st.caption("Circles mark correct answers, crosses mark incorrect answers, and diamonds mark the predicted "
               "point at which mastery falls to 50%. Hover over any point for exact values.")

    bar_col, tbl_col = st.columns([1, 1.6], gap="large")
    with bar_col:
        names = list(S.concepts)
        vals = [mastery_at(S.concepts[n], S.t) * 100 for n in names]
        bar = go.Figure(go.Bar(
            x=vals, y=names, orientation="h", text=[f"{v:.0f}%" for v in vals], textposition="outside",
            marker_color=["#15803d" if v >= 70 else "#b45309" if v >= 50 else "#b91c1c" for v in vals]))
        bar.update_layout(template="plotly_white", height=230, margin=dict(l=10, r=30, t=40, b=10),
                          title=dict(text="Mastery right now", font=dict(size=14)),
                          xaxis=dict(range=[0, 115], ticksuffix="%", showgrid=False))
        st.plotly_chart(bar, width="stretch")
    with tbl_col:
        rows = []
        for n, k in S.concepts.items():
            tr, tf = time_to_threshold(k, T_REVIEW), time_to_threshold(k, T_FORGET)
            rows.append({
                "Concept": n, "Memory strength": fmt_dur(k.stability),
                "Revise before": "Revise now" if tr is None or tr <= S.t else clock(tr),
                "Mastery falls to 50%": "Not learned yet" if tf is None else
                                        "Already below 50%" if tf <= S.t else clock(tf)})
        st.markdown("**Revision schedule**")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ---------- Method ----------
with tab_math:
    sel = st.selectbox("Concept", list(S.bank), key="math_concept")
    tr = S.concepts[sel].last_trace
    if not tr:
        st.info("Answer a question for this concept first. The exact calculation for the last answer appears here.")
    else:
        st.markdown(f"Calculation for the last answer ({'correct' if tr['correct'] else 'incorrect'}).")
        st.markdown(f"**Step 1. Forgetting before the answer.** {tr['dt']:.0f} minutes passed since the last practice.")
        st.latex(r"R = e^{-\Delta t / S} = e^{-" + f"{tr['dt']:.0f}/{tr['S_old']:.0f}" + r"} = " + f"{tr['R']:.3f}")
        st.latex(r"P(L)_{prior} = P(L) \times R = " + f"{tr['p_before']:.3f} \\times {tr['R']:.3f} = {tr['prior']:.3f}")
        if tr["correct"]:
            st.markdown("**Step 2. Bayesian update (correct answer).**")
            st.latex(r"P(L\,|\,correct) = \frac{P(L)(1-slip)}{P(L)(1-slip) + (1-P(L))\,guess}")
        else:
            st.markdown("**Step 2. Bayesian update (incorrect answer).**")
            st.latex(r"P(L\,|\,wrong) = \frac{P(L)\,slip}{P(L)\,slip + (1-P(L))(1-guess)}")
        st.latex(f"= \\frac{{{tr['num']:.3f}}}{{{tr['den']:.3f}}} = {tr['post']:.3f}")
        st.markdown("**Step 3. Learning from the attempt.**")
        st.latex(r"P(L)_{new} = post + (1-post)\times T = " +
                 f"{tr['post']:.3f} + {1 - tr['post']:.3f} \\times {tr['transit']:.2f} = {tr['p_new']:.3f}")
        mult = tr["gain"] if tr["correct"] else tr["loss"]
        st.markdown("**Step 4. Change in memory strength.**")
        st.latex(f"S_{{new}} = S \\times {mult:.2f} = {tr['S_old']:.0f} \\times {mult:.2f} = {tr['S_new']:.0f}\\ \\text{{min}}")
        st.markdown("**Step 5. Time until mastery falls to 50%.**")
        if tr["p_new"] > T_FORGET:
            tmin = tr["S_new"] * math.log(tr["p_new"] / T_FORGET)
            st.latex(r"t = S \ln\!\left(\frac{P(L)}{0.5}\right) = " +
                     f"{tr['S_new']:.0f} \\ln({tr['p_new']:.3f}/0.5) = {tmin:.0f}\\ \\text{{min}}")
            st.success(f"Predicted: mastery falls to 50% about {fmt_dur(tmin)} after this answer, at {clock(tr['t'] + tmin)}.")
        else:
            st.warning("Mastery is at or below 50%, so this concept is treated as not yet learned.")
    with st.expander("Model assumptions"):
        st.markdown(
            "- Bayesian Knowledge Tracing and the Ebbinghaus forgetting curve are established models.\n"
            "- The four BKT parameters are typical assumed values. A deployed system would estimate them from student data.\n"
            "- The memory strength multipliers (1.8 and 0.7) are a simple heuristic for the spacing effect.\n"
            "- Predicted forgetting times are model estimates and not guarantees for an individual student.")

# ---------- Progress ----------
with tab_progress:
    rows = []
    for n in S.bank:
        a_, c_ = S.stats["attempted"].get(n, 0), S.stats["correct"].get(n, 0)
        rows.append({"Concept": n, "Attempted": a_, "Solved": c_, "Accuracy": f"{c_ / a_:.0%}" if a_ else "n/a"})
    l, r = st.columns([1, 1.2], gap="large")
    with l:
        st.markdown("**Questions by concept**")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.markdown("**Activity, last 7 days**")
        visited = set(S.stats["visit_dates"])
        for i, col in enumerate(st.columns(7)):
            d = date.today() - timedelta(days=6 - i)
            fill = "#1e3a8a" if d.isoformat() in visited else "#e2e8f0"
            col.markdown(
                f"<div style='text-align:center'><div style='width:32px;height:32px;margin:0 auto;"
                f"border-radius:6px;background:{fill}'></div>"
                f"<div style='font-size:0.72rem;color:#64748b;margin-top:4px'>{d:%a}</div></div>",
                unsafe_allow_html=True)
        st.caption(f"Saved in {PROGRESS.name}. Days active increases by one for each new day the app is opened.")
    with r:
        gb = go.Figure()
        gb.add_bar(name="Attempted", x=list(S.bank), y=[x["Attempted"] for x in rows], marker_color="#94a3b8")
        gb.add_bar(name="Solved", x=list(S.bank), y=[x["Solved"] for x in rows], marker_color="#1e3a8a")
        gb.update_layout(template="plotly_white", barmode="group", height=320, margin=dict(l=10, r=10, t=30, b=10),
                         legend=dict(orientation="h", y=1.1), yaxis=dict(dtick=1, rangemode="tozero"))
        st.plotly_chart(gb, width="stretch")

    st.markdown("**Milestones**")
    badges = [("First question solved", cor >= 1), ("10 questions solved", cor >= 10),
              ("3-day streak", strk >= 3), ("One concept mastered", mastered >= 1),
              ("All concepts mastered", mastered == len(S.bank))]
    for col, (label, got) in zip(st.columns(len(badges)), badges):
        col.markdown(f"<div style='text-align:center'>{chip('Earned', 'green') if got else chip('Locked', 'grey')}"
                     f"<div style='font-size:0.82rem;margin-top:6px'>{label}</div></div>", unsafe_allow_html=True)

    report = []
    for n, k in S.concepts.items():
        tr_, tf_ = time_to_threshold(k, T_REVIEW), time_to_threshold(k, T_FORGET)
        report.append({
            "Concept": n, "Attempted": S.stats["attempted"].get(n, 0), "Solved": S.stats["correct"].get(n, 0),
            "Mastery now (%)": round(mastery_at(k, S.t) * 100, 1),
            "Memory strength (min)": round(k.stability),
            "Revise before": "Revise now" if tr_ is None or tr_ <= S.t else clock(tr_),
            "Mastery falls to 50%": "Not learned yet" if tf_ is None else
                                    "Already below 50%" if tf_ <= S.t else clock(tf_)})
    st.write("")
    st.download_button("Download progress report (CSV)", pd.DataFrame(report).to_csv(index=False),
                       file_name="progress_report.csv", mime="text/csv")

# ---------- Question bank ----------
with tab_add:
    st.markdown("### Add questions")
    st.caption("Questions are saved in questions.json next to app.py and remain after the app is restarted.")
    if S.flash:
        st.success(S.flash)
        S.flash = None
    with st.form("add_q", clear_on_submit=True):
        target = st.selectbox("Concept", list(S.bank) + ["New concept"])
        new_name = st.text_input("New concept name (only when 'New concept' is selected)")
        qtext = st.text_input("Question")
        o1, o2 = st.columns(2)
        options = [o1.text_input("Option 1"), o2.text_input("Option 2"),
                   o1.text_input("Option 3"), o2.text_input("Option 4")]
        correct_no = st.selectbox("Correct option", [1, 2, 3, 4])
        submitted = st.form_submit_button("Add question", type="primary")
    if submitted:
        concept = new_name.strip() if target == "New concept" else target
        opts = [x.strip() for x in options]
        if not concept or not qtext.strip() or not all(opts) or len(set(opts)) < 4:
            st.error("Enter the concept, the question, and four different options.")
        else:
            save_custom_question(concept, qtext.strip(), opts, correct_no - 1)
            S.bank.setdefault(concept, []).append((qtext.strip(), opts, correct_no - 1))
            if concept not in S.concepts:
                S.concepts[concept] = Concept(concept, P_INIT)
                S.idx[concept] = 0
            S.flash = f"Question added to {concept}. It now has {len(S.bank[concept])} questions."
            st.rerun()
    st.markdown("**Question bank summary**")
    st.dataframe(pd.DataFrame([{"Concept": n, "Questions": len(v)} for n, v in S.bank.items()]),
                 hide_index=True, width="stretch")
