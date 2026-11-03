"""Compute desired outputs only. No HA imports, network or device execution."""

from copy import deepcopy
from string import Formatter

from .const import HISTORY_LIMIT, MAX_LONG_TEXT
from .output_config import template_fields
from .notification import alarm_context


def _unique(values):
    return list(dict.fromkeys(values))


def plan_outputs(outputs, bindings, rules, session, targets=None):
    targets = targets or {}
    enabled_rules = {rule.id for rule in rules if rule.enabled}
    result = {}
    for output in outputs:
        alarms = [record for rule_id, record in session.alarms.items()
                  if rule_id in enabled_rules and output.id in bindings.get(rule_id, [])]
        phase = "alarm" if any(item["state"] == "active" for item in alarms) else "acknowledged" if alarms else "idle"
        target = targets.get(output.id, {"entity_id": output.entity_id, "available": True, "min_length": 0, "max_length": 255})
        record = {"id": output.id, "name": output.name, "kind": output.kind, "entity_id": target["entity_id"],
                  "phase": phase, "status": "planned", "value": None, "error": None,
                  "rules": [{"id": item["rule_id"], "name": item["rule_name"]} for item in alarms]}
        result[output.id] = record
        if not output.enabled:
            record["status"] = "disabled"
            continue
        if output.kind == "switch":
            requests = [output.alarm_value if item["state"] == "active" else output.acknowledged_value for item in alarms]
            record["value"] = ("on" if "on" in requests else "off") if requests else output.idle_value
        else:
            template = {"alarm": output.alarm_value, "acknowledged": output.acknowledged_value, "idle": output.idle_value}[phase]
            sources = [source for alarm in alarms for source in alarm["sources"]]
            context = {"regel": ", ".join(_unique(item["rule_name"] for item in alarms)),
                       "quelle": ", ".join(_unique(item["name"] for item in sources)),
                       "bereich": ", ".join(_unique(item["area_name"] or "Ohne Bereich" for item in sources)),
                       "alarmtyp": ", ".join(_unique({"house": "Hausalarm", "fire": "Feuer", "intrusion": "Einbruch"}[item["alarm_type"]] for item in alarms)),
                       "status": {"alarm": "aktiv", "acknowledged": "quittiert", "idle": "Ruhezustand"}[phase]}
            template_fields(template)
            value = Formatter().vformat(template, (), context)
            record["value"] = value
            if len(value) > MAX_LONG_TEXT:
                record["error"] = "text_too_long"
                record["value"] = value[:MAX_LONG_TEXT]
            elif output.kind == "short_text":
                try:
                    if any(character in value for character in ("\x00", "\n", "\r")):
                        record["error"] = "short_text_invalid"
                    elif len(value.encode(output.encoding)) > 14:
                        record["error"] = "short_text_too_long"
                except UnicodeEncodeError:
                    record["error"] = "unsupported_character"
            elif "\x00" in value:
                record["error"] = "invalid_text_character"
            if output.kind in ('notification', 'overlay'):
                title = Formatter().vformat(output.notification['title'], (), alarm_context(alarms,phase))
                if len(value) > 1024 or len(title) > 80:
                    record['error'] = 'notification_too_long'
            if output.entity_id and not record["error"]:
                if not target.get("min_length", 0) <= len(value) <= target.get("max_length", 255):
                    record["error"] = "target_text_length"
        if output.entity_id and not target.get("available", True):
            record["error"] = record["error"] or "target_unavailable"
        if record["error"]:
            record["status"] = "error"
    return result


def apply_output_plan(session, outputs, bindings, rules, now, targets=None):
    result = deepcopy(session)
    plan = plan_outputs(outputs, bindings, rules, session, targets)
    for output_id in dict.fromkeys([*result.output_plan, *plan]):
        previous = result.output_plan.get(output_id)
        current = plan.get(output_id)
        if previous != current:
            event = deepcopy(current or dict(previous, status="removed", value=None))
            event["time"] = now
            result.output_history.append(event)
    result.output_history[:] = result.output_history[-HISTORY_LIMIT:]
    result.output_plan = plan
    return result
