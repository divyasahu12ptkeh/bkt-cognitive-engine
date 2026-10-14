from datetime import datetime
from typing import Dict, Any

class StateManager:
    def __init__(self):
        self.db: Dict[str, Dict[str, Any]] = {}

    def _get_key(self, student_id: str, concept_id: str) -> str:
        return f"{student_id}:{concept_id}"

    def get_or_create(self, student_id: str, concept_id: str) -> Dict[str, Any]:
        key = self._get_key(student_id, concept_id)
        if key not in self.db:
            self.db[key] = {
                "student_id": student_id,
                "concept_id": concept_id,
                "p_l": 0.10,
                "stability": 60.0,
                "streak": 0,
                "last_updated": datetime.now(),
                "virtual_time_offset_min": 0
            }
        return self.db[key]

    def update_state(self, student_id: str, concept_id: str, updates: dict):
        key = self._get_key(student_id, concept_id)
        if key in self.db:
            self.db[key].update(updates)

state_manager = StateManager()
