"""Read-only presentation helpers; no alarm mutations or external actions."""

from collections import Counter
import re

from .input_config import InputValidationError

RULE_SECTIONS = {"when": {"input_ids", "mode"}, "then": {"alarm_type", "output_ids"}}
OUTPUT_SECTIONS = {"alarm": {"alarm_value"}, "acknowledged": {"acknowledged_value"},
                   "idle": {"idle_value"}, "format": {"encoding"}, "delivery": {"routes", "title"}, "pushover": {"devices", "priority"}}
STATUS_LABELS = {"matching": "Ausgelöst", "not_matching": "Normal", "disabled": "Deaktiviert",
                 "missing": "Fehlt", "unknown": "Unbekannt", "unavailable": "Nicht verfügbar", "blocked": "Gesperrt"}
DELIVERY_LABELS = {"pending": "Wird ausgeführt", "sent": "Rückmeldung offen", "confirmed": "Bestätigt",
                   "failed": "Fehler", "mismatch": "Zustand abweichend", "internal": "Intern aktualisiert", "idle": "Nicht angefordert"}
KIND_LABELS = {"switch": "Schalten", "short_text": "Kurztext", "long_text": "Langtext", "notification": "Push-Nachricht", "overlay": "Tablet-Overlay"}


def flatten_sections(data, sections):
    """Keep HA section nesting at the form boundary, never in stored models."""
    if not isinstance(data, dict):
        raise InputValidationError("base", "invalid_input")
    result = dict(data)
    for name, fields in sections.items():
        if name not in result:
            continue
        values = result.pop(name)
        if not isinstance(values, dict) or not set(values) <= fields or set(values) & set(result):
            raise InputValidationError("base", "invalid_input")
        result.update(values)
    return result


def section_errors(errors, sections):
    return {next((section for section, fields in sections.items() if field in fields), field): error
            for field, error in errors.items()}


def markdown_text(value):
    """Names remain text, even when users include Markdown or newlines."""
    text = " ".join(str(value).split())
    return re.sub(r"([\\`*_{}\[\]<>|])", r"\\\1", text)


def selection_labels(items):
    counts = Counter(item.name for item in items)
    return {item.id: f"{item.name} · {'aktiviert' if item.enabled else 'deaktiviert'}" +
            (f" · {item.entity_id}" if counts[item.name] > 1 and getattr(item, "entity_id", None) else "") for item in items}


def runtime_summary(manager):
    if manager is None or not hasattr(manager, "session"):
        return {"state": "Nicht geladen", "alarms": "—", "source_errors": "—", "output_errors": "—"}
    session = manager.session
    source_errors = sum(item["status"] in ("missing", "unknown", "unavailable", "blocked") for item in manager.inputs.snapshot)
    errors = {key for key, item in session.output_plan.items() if item["status"] == "error"}
    errors.update(key for key, item in session.executions.items() if key in session.output_plan and item["status"] in ("failed", "mismatch"))
    errors.update(manager.delivery_failures)
    return {"state": {"idle": "Ruhezustand", "active": "Alarm aktiv", "acknowledged": "Quittiert"}[session.state],
            "alarms": str(len(session.alarms) + (session.manual.state != "idle")),
            "source_errors": str(source_errors), "output_errors": str(len(errors))}
