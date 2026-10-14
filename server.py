import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime, timezone, timedelta
from pathlib import Path
from math_engine import BKTEngine

engine = BKTEngine()
db = {}  # Session state: "user_id:concept_id" -> state

STATIC_DIR = Path(__file__).resolve().parent / "static"

def get_state(user_id: str, concept_id: str):
    key = f"{user_id}:{concept_id}"
    if key not in db:
        db[key] = {
            "p_l": engine.p_init,
            "streak": 0,
            "stability": engine.calculate_stability(engine.p_init, 0),
            "last_updated": datetime.now(timezone.utc)
        }
    return db[key]

class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def _send_json(self, status: int, payload: dict):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._send_cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        # Serve index.html at root
        if self.path == "/" or self.path == "":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            body = self._read_body()
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        user_id = body.get("user_id", "demo_user")
        concept_id = body.get("concept_id", "bayes_101")

        if path == "/api/attempt":
            correct = bool(body.get("correct", False))
            state = get_state(user_id, concept_id)
            now = datetime.now(timezone.utc)

            state["streak"] = (state["streak"] + 1) if correct else 0
            state["p_l"] = engine.update_mastery(state["p_l"], correct)
            state["stability"] = engine.calculate_stability(state["p_l"], state["streak"])
            state["last_updated"] = now

            t_forget = engine.time_to_forget(state["stability"], 0.70)
            target_dt = now + timedelta(minutes=t_forget)

            self._send_json(200, {
                "concept_id": concept_id,
                "mastery_probability": round(state["p_l"], 3),
                "current_retrievability": 1.0,
                "memory_stability_minutes": round(state["stability"], 1),
                "predicted_forget_minute": target_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "minutes_until_review": int(t_forget)
            })

        elif path == "/api/time-travel":
            mins = float(body.get("minutes_forward", 0.0))
            state = get_state(user_id, concept_id)
            r = engine.retrievability(mins, state["stability"])
            t_total = engine.time_to_forget(state["stability"], 0.70)
            mins_left = max(0, t_total - mins)

            self._send_json(200, {
                "concept_id": concept_id,
                "mastery_probability": round(state["p_l"], 3),
                "current_retrievability": round(r, 3),
                "elapsed_minutes": mins,
                "minutes_until_review": int(mins_left)
            })
        else:
            self._send_json(404, {"error": "Not Found"})

if __name__ == "__main__":
    os.makedirs(STATIC_DIR, exist_ok=True)
    server = HTTPServer(("", 8000), AppHandler)
    print("Serving on http://localhost:8000")
    server.serve_forever()