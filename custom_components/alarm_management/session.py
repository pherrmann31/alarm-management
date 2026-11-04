"""Pure, persistent alarm session: latched sources plus a bounded journal."""

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime

from .alarm_engine import AlarmState, transition
from .const import ALARM_TYPES, HISTORY_LIMIT
from .rule_config import default_rule_id, default_rule_name
from .rule_engine import SOURCE_FIELDS
from .output_config import KINDS, PHASES
from .const import MAX_LONG_TEXT
from .notification import reset_error_message

EVENT_LABELS = {
    "source_triggered": "Eingang ausgelöst", "source_cleared": "Eingang wieder normal",
    "trigger_test": "Manueller Testalarm", "acknowledge": "Alarme quittiert",
    "reset": "Alarme zurückgesetzt", "reset_blocked": "Reset blockiert",
    "rule_triggered": "Regel ausgelöst", "rule_cleared": "Regel nicht mehr erfüllt",
    "rule_source_added": "Weitere Quelle zur Regel",
    "popup_acknowledged": "Quittierung im Browser übernommen",
    "popup_acknowledge_rejected": "Browser-Quittierung nicht übernommen",
}


def _timestamp(value):
    if not isinstance(value, str) or datetime.fromisoformat(value).tzinfo is None:
        raise ValueError("Invalid alarm timestamp")


@dataclass
class AlarmSession:
    manual: AlarmState = field(default_factory=AlarmState)
    alarms: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    output_plan: dict = field(default_factory=dict)
    output_history: list = field(default_factory=list)
    executions: dict = field(default_factory=dict)
    delivery_history: list = field(default_factory=list)

    @property
    def state(self):
        states = [self.manual.state, *(item["state"] for item in self.alarms.values())]
        return "active" if "active" in states else "acknowledged" if "acknowledged" in states else "idle"

    def to_dict(self):
        return {"execution_mode": "live", "alarm": self.manual.to_dict(),
                "source_alarms": deepcopy(self.alarms), "history": deepcopy(self.history),
                "output_plan": deepcopy(self.output_plan), "output_history": deepcopy(self.output_history),
                "executions": deepcopy(self.executions), "delivery_history": deepcopy(self.delivery_history)}

    @classmethod
    def from_dict(cls, data):
        if (not isinstance(data, dict) or set(data) != {"execution_mode", "alarm", "source_alarms", "history", "output_plan", "output_history", "executions", "delivery_history"}
                or data["execution_mode"] != "live" or not isinstance(data["source_alarms"], dict)
                or not isinstance(data["history"], list) or len(data["history"]) > HISTORY_LIMIT):
            raise ValueError("Invalid alarm session")
        fields = {"id", "name", "entity_id", "alarm_type", "area_id", "area_name", "state", "triggered_at", "condition_cleared",
                  "rule_id", "rule_name", "input_ids", "sources", "matching_input_ids"}
        for source_id, record in data["source_alarms"].items():
            if not isinstance(record, dict) or set(record) != fields or source_id != record["id"]:
                raise ValueError("Invalid source alarm")
            if not all(isinstance(record[key], str) and record[key] for key in ("id", "name", "entity_id")):
                raise ValueError("Invalid source identity")
            if record["state"] not in ("active", "acknowledged") or record["alarm_type"] not in ALARM_TYPES:
                raise ValueError("Invalid source alarm state")
            if type(record["condition_cleared"]) is not bool:
                raise ValueError("Invalid source alarm condition")
            for key in ("area_id", "area_name"):
                if record[key] is not None and not isinstance(record[key], str):
                    raise ValueError("Invalid alarm area")
            _timestamp(record["triggered_at"])
            if record["rule_id"] != source_id or not isinstance(record["rule_name"], str) or not record["rule_name"]:
                raise ValueError("Invalid alarm rule identity")
            if not isinstance(record["input_ids"], list) or not record["input_ids"] or not all(isinstance(item, str) for item in record["input_ids"]):
                raise ValueError("Invalid alarm input references")
            if not isinstance(record["sources"], list) or not record["sources"]:
                raise ValueError("Invalid alarm contributors")
            if (not isinstance(record["matching_input_ids"], list) or
                    not all(isinstance(item, str) for item in record["matching_input_ids"]) or
                    not set(record["matching_input_ids"]) <= set(record["input_ids"])):
                raise ValueError("Invalid matching inputs")
            for source in record["sources"]:
                if not isinstance(source, dict) or set(source) != set(SOURCE_FIELDS) or not all(isinstance(source[key], str) for key in ("id", "name", "entity_id")):
                    raise ValueError("Invalid alarm contributor")
        for record in data["history"]:
            if (not isinstance(record, dict) or set(record) != {"time", "event", "message", "sources"}
                    or record["event"] not in EVENT_LABELS or not isinstance(record["message"], str)
                    or not isinstance(record["sources"], list)):
                raise ValueError("Invalid journal record")
            _timestamp(record["time"])
            for source in record["sources"]:
                if not isinstance(source, dict) or not all(isinstance(source.get(key), str) for key in ("id", "name", "entity_id")):
                    raise ValueError("Invalid journal source")
        if (not isinstance(data["output_plan"], dict) or not isinstance(data["output_history"], list)
                or len(data["output_history"]) > HISTORY_LIMIT):
            raise ValueError("Invalid output session")
        for output_id, record in data["output_plan"].items():
            _validate_output_record(record)
            if record["id"] != output_id:
                raise ValueError("Invalid output plan ID")
        for record in data["output_history"]:
            _validate_output_record(record, history=True)
        if not isinstance(data["executions"], dict) or not isinstance(data["delivery_history"], list) or len(data["delivery_history"]) > HISTORY_LIMIT:
            raise ValueError("Invalid delivery state")
        for output_id, record in data["executions"].items():
            _validate_delivery(record)
            if record["output_id"] != output_id:
                raise ValueError("Invalid delivery ID")
        for record in data["delivery_history"]:
            _validate_delivery(record)
        return cls(AlarmState.from_dict(data["alarm"]), deepcopy(data["source_alarms"]), deepcopy(data["history"]),
                   deepcopy(data["output_plan"]), deepcopy(data["output_history"]), deepcopy(data["executions"]), deepcopy(data["delivery_history"]))


def _validate_delivery(record):
    fields = {"output_id", "name", "entity_id", "target_id", "value", "status", "error", "time", "owned"}
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError("Invalid delivery fields")
    if record["status"] not in ("pending", "sent", "confirmed", "failed", "mismatch", "internal", "idle") or type(record["owned"]) is not bool:
        raise ValueError("Invalid delivery status")
    for key in ("output_id", "name", "entity_id", "target_id", "value", "error"):
        if record[key] is not None and (not isinstance(record[key], str) or len(record[key]) > MAX_LONG_TEXT):
            raise ValueError("Invalid delivery data")
    if not record["output_id"] or not record["name"]:
        raise ValueError("Invalid delivery identity")
    if record["owned"] and (not record["entity_id"] or not record["target_id"] or record["value"] is None):
        raise ValueError("Invalid controlled target identity")
    _timestamp(record["time"])


def _validate_output_record(record, history=False):
    fields = {"id", "name", "kind", "entity_id", "phase", "status", "value", "error", "rules"}
    if history:
        fields.add("time")
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError("Invalid output plan fields")
    if not all(isinstance(record[key], str) and record[key] for key in ("id", "name")):
        raise ValueError("Invalid output identity")
    if record["kind"] not in KINDS or record["phase"] not in PHASES or record["status"] not in ("planned", "disabled", "error", "removed"):
        raise ValueError("Invalid output plan status")
    for key in ("value", "error", "entity_id"):
        if record[key] is not None and (not isinstance(record[key], str) or len(record[key]) > MAX_LONG_TEXT):
            raise ValueError("Invalid output plan value")
    if not isinstance(record["rules"], list) or not all(isinstance(item, dict) and set(item) == {"id", "name"} and all(isinstance(value, str) for value in item.values()) for item in record["rules"]):
        raise ValueError("Invalid output contributors")
    if history:
        _timestamp(record["time"])


def append_event(session, event, now, sources=()):
    sources = [deepcopy(item) for item in sources]
    names = ", ".join(item["name"] for item in sources)
    if event in ("rule_triggered", "rule_source_added"):
        names = ", ".join(f"{item['rule_name']} ({', '.join(source['name'] for source in item['sources'])})" for item in sources)
    message = EVENT_LABELS[event] + (f": {names}" if names else "")
    if event=='reset_blocked':
        message=reset_error_message(sources)
    session.history.append({"time": now, "event": event, "message": message, "sources": sources})
    session.history[:] = session.history[-HISTORY_LIMIT:]


def reconcile(session, snapshot, now):
    """Latch matching sources. A clear condition does not reset the alarm."""
    result = deepcopy(session)
    for item in snapshot:
        previous = result.alarms.get(item["id"])
        if item["status"] == "matching" and (previous is None or previous["condition_cleared"]):
            record = {key: item.get(key) for key in ("id", "name", "entity_id", "alarm_type", "area_id", "area_name")}
            record.update(state="active", triggered_at=now, condition_cleared=False)
            record.update(rule_id=item.get("rule_id", item["id"]), rule_name=item.get("rule_name", item["name"]),
                          input_ids=list(item.get("input_ids", [item["id"]])),
                          sources=deepcopy(item.get("sources") or [{key: item.get(key) for key in SOURCE_FIELDS}]))
            record["matching_input_ids"] = [source["id"] for source in record["sources"]]
            result.alarms[item["id"]] = record
            append_event(result, "rule_triggered" if "rule_id" in item else "source_triggered", now, [record])
        elif item["status"] == "matching" and previous and "sources" in item:
            previous["input_ids"] = list(dict.fromkeys([*previous["input_ids"], *item["input_ids"]]))
            known = {source["id"] for source in previous["sources"]}
            added = [source for source in item["sources"] if source["id"] not in known]
            rising = [source for source in item["sources"] if source["id"] not in previous["matching_input_ids"]]
            uncertain = [input_id for input_id in previous["matching_input_ids"]
                         if item.get("input_states", {}).get(input_id) in ("unknown", "unavailable", "missing", "blocked", "disabled")]
            previous["matching_input_ids"] = list(dict.fromkeys([*(source["id"] for source in item["sources"]), *uncertain]))
            if added:
                previous["sources"].extend(deepcopy(added))
            if rising:
                previous["state"] = "active"
                append_event(result, "rule_source_added", now, [previous])
        elif item["status"] == "not_matching" and previous and not previous["condition_cleared"]:
            previous["condition_cleared"] = True
            previous["matching_input_ids"] = []
            append_event(result, "rule_cleared" if "rule_id" in item else "source_cleared", now, [previous])
    return result


def apply_action(session, action, snapshot, now, rule_ids=None):
    if rule_ids is not None and action!='acknowledge':
        raise ValueError('Scoped action must be acknowledgement')
    result = reconcile(session, snapshot, now)
    if action == "reset":
        blocked = [item for item in snapshot if item["status"] == "matching" or
                   (item["id"] in result.alarms and item["enabled"] and item["status"] in
                    ("unknown", "unavailable", "missing", "blocked"))]
        if blocked:
            append_event(result, "reset_blocked", now, blocked)
            return result, False
        if result.alarms or result.manual.state != "idle":
            append_event(result, "reset", now, result.alarms.values())
        result.alarms = {}
    elif action == "acknowledge":
        changed = [item for item in result.alarms.values() if item["state"] == "active" and (rule_ids is None or item['rule_id'] in rule_ids)]
        if changed or (rule_ids is None and result.manual.state == "active"):
            append_event(result, action, now, changed)
        for record in result.alarms.values():
            if rule_ids is None or record['rule_id'] in rule_ids:
                record["state"] = "acknowledged"
    elif action == "trigger_test":
        append_event(result, action, now)
    # transition validates action names and retains the existing manual test counter.
    if rule_ids is None:
        result.manual = transition(result.manual, action, now)
    return result, True


def migrate_v2_session(data):
    """Convert latched v0.3 source alarms to the corresponding default rules."""
    if (not isinstance(data, dict) or set(data) != {"simulation", "alarm", "source_alarms", "history"}
            or data["simulation"] is not True or not isinstance(data["source_alarms"], dict)):
        raise ValueError("Invalid version-2 alarm store")
    result = deepcopy(data)
    result["source_alarms"] = {}
    old_fields = {"id", "name", "entity_id", "alarm_type", "area_id", "area_name", "state", "triggered_at", "condition_cleared"}
    for input_id, old in data["source_alarms"].items():
        if not isinstance(old, dict) or set(old) != old_fields or old["id"] != input_id:
            raise ValueError("Invalid legacy source alarm")
        record = deepcopy(old)
        rule_id = default_rule_id(input_id)
        record.update(id=rule_id, name=default_rule_name(old["name"]), rule_id=rule_id,
                      rule_name=default_rule_name(old["name"]), input_ids=[input_id],
                      matching_input_ids=[] if old["condition_cleared"] else [input_id],
                      sources=[{key: deepcopy(old[key]) for key in SOURCE_FIELDS}])
        result["source_alarms"][rule_id] = record
    return migrate_v3_session(result)


def migrate_v3_session(data):
    if not isinstance(data, dict) or set(data) != {"simulation", "alarm", "source_alarms", "history"}:
        raise ValueError("Invalid version-3 alarm store")
    result = deepcopy(data)
    result.update(output_plan={}, output_history=[])
    return migrate_v4_session(result)


def migrate_v4_session(data):
    if (not isinstance(data, dict) or set(data) != {"simulation", "alarm", "source_alarms", "history", "output_plan", "output_history"}
            or data["simulation"] is not True):
        raise ValueError("Invalid version-4 alarm store")
    result = deepcopy(data)
    result.pop("simulation")
    result.update(execution_mode="live", executions={}, delivery_history=[])
    for record in [*result["output_plan"].values(), *result["output_history"]]:
        if record.get("status") == "simulation":
            record["status"] = "planned"
    return AlarmSession.from_dict(result).to_dict()
