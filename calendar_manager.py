"""Calendar / reminder manager for Nicky AI — JSON-backed event store."""
import json
import os
import uuid
from datetime import datetime, timedelta, date as date_type


class CalendarManager:
    """Manages events and reminders stored in nicky_data/calendar.json.

    Event schema:
        {
            "id": str,
            "title": str,
            "date": "YYYY-MM-DD",
            "time": "HH:MM" or "",
            "notes": str,
            "reminded": bool
        }
    """

    DATE_FMTS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d %Y", "%b %d %Y",
                 "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"]
    TIME_FMTS = ["%H:%M", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p"]

    def __init__(self, data_dir: str = "nicky_data"):
        self._path = os.path.join(data_dir, "calendar.json")
        self._events: list[dict] = []
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    self._events = json.load(f)
            except Exception:
                self._events = []
        else:
            self._events = []

    def _save(self):
        try:
            with open(self._path, "w") as f:
                json.dump(self._events, f, indent=2)
        except Exception:
            pass

    # ── Parsing helpers ───────────────────────────────────────────────────────

    def _parse_date(self, text: str) -> str | None:
        """Return YYYY-MM-DD string or None."""
        text = text.strip()
        today = datetime.today()
        lower = text.lower()

        if lower in ("today", "now"):
            return today.strftime("%Y-%m-%d")
        if lower == "tomorrow":
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        if lower in ("next week", "this week"):
            return (today + timedelta(weeks=1)).strftime("%Y-%m-%d")

        # Day names e.g. "next monday"
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, d in enumerate(days):
            if d in lower:
                delta = (i - today.weekday()) % 7 or 7
                return (today + timedelta(days=delta)).strftime("%Y-%m-%d")

        # Explicit date formats
        for fmt in self.DATE_FMTS:
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _parse_time(self, text: str) -> str:
        """Return HH:MM string or empty string."""
        text = text.strip()
        for fmt in self.TIME_FMTS:
            try:
                return datetime.strptime(text, fmt).strftime("%H:%M")
            except ValueError:
                continue
        return ""

    # ── Public API ────────────────────────────────────────────────────────────

    def add_event(self, title: str, date_text: str, time_text: str = "",
                  notes: str = "") -> str:
        date_str = self._parse_date(date_text)
        if not date_str:
            return f"I couldn't understand that date: '{date_text}'. Try something like 'tomorrow' or 'April 10'."
        time_str = self._parse_time(time_text) if time_text else ""
        event = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "date": date_str,
            "time": time_str,
            "notes": notes,
            "reminded": False,
        }
        self._events.append(event)
        self._save()
        time_part = f" at {time_str}" if time_str else ""
        return f"📅 Added '{title}' on {date_str}{time_part}. (ID: {event['id']})"

    def list_events(self, scope: str = "today") -> str:
        today = datetime.today()
        today_str = today.strftime("%Y-%m-%d")

        if scope == "today":
            events = [e for e in self._events if e["date"] == today_str]
            label = "today"
        elif scope == "week":
            end = (today + timedelta(days=7)).strftime("%Y-%m-%d")
            events = [e for e in self._events if today_str <= e["date"] <= end]
            label = "this week"
        else:
            events = sorted(self._events, key=lambda e: e["date"])
            label = "all upcoming"

        if not events:
            return f"No events scheduled for {label}."

        events = sorted(events, key=lambda e: (e["date"], e["time"] or "23:59"))
        lines = [f"📅 Calendar — {label}:"]
        for e in events:
            time_part = f" @ {e['time']}" if e["time"] else ""
            notes_part = f"  [{e['notes']}]" if e.get("notes") else ""
            lines.append(f"  [{e['id']}] {e['date']}{time_part}  {e['title']}{notes_part}")
        return "\n".join(lines)

    def delete_event(self, event_id: str) -> str:
        before = len(self._events)
        self._events = [e for e in self._events if e["id"] != event_id]
        if len(self._events) < before:
            self._save()
            return f"🗑 Deleted event {event_id}."
        return f"No event found with ID '{event_id}'."

    def get_reminders_due(self, window_minutes: int = 15) -> list[dict]:
        """Return events within the next window_minutes that haven't been reminded."""
        now = datetime.now()
        due = []
        for e in self._events:
            if e.get("reminded"):
                continue
            if not e.get("time"):
                continue
            try:
                event_dt = datetime.strptime(f"{e['date']} {e['time']}", "%Y-%m-%d %H:%M")
                delta = (event_dt - now).total_seconds() / 60
                if 0 <= delta <= window_minutes:
                    due.append(e)
            except ValueError:
                continue
        return due

    def mark_reminded(self, event_id: str):
        for e in self._events:
            if e["id"] == event_id:
                e["reminded"] = True
        self._save()
