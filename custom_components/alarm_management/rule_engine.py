"""Pure three-valued UND/ODER evaluation, with no HA or device calls."""

from copy import deepcopy

SOURCE_FIELDS = ("id", "name", "entity_id", "area_id", "area_name")


def evaluate_rules(rules, snapshot):
    inputs = {item["id"]: item for item in snapshot}
    result = []
    for rule in rules:
        items = [inputs.get(input_id) for input_id in rule.input_ids]
        states = [item["status"] if item else "missing" for item in items]
        if not rule.enabled:
            status = "disabled"
        elif not states:
            status = "unknown"
        elif rule.mode == "any":
            status = ("matching" if "matching" in states else
                      "not_matching" if all(state == "not_matching" for state in states) else "unknown")
        else:
            status = ("not_matching" if "not_matching" in states else
                      "matching" if all(state == "matching" for state in states) else "unknown")
        contributors = [{key: deepcopy(item.get(key)) for key in SOURCE_FIELDS}
                        for item in items if item and item["status"] == "matching"]
        areas = list(dict.fromkeys(item["area_name"] or "Ohne Bereich" for item in contributors))
        result.append({
            "id": rule.id, "rule_id": rule.id, "rule_name": rule.name, "name": rule.name,
            "entity_id": contributors[0]["entity_id"] if contributors else f"rule.{rule.id}",
            "alarm_type": rule.alarm_type, "enabled": rule.enabled, "mode": rule.mode,
            "input_ids": list(rule.input_ids), "sources": contributors,
            "input_states": dict(zip(rule.input_ids, states, strict=True)),
            "area_id": contributors[0]["area_id"] if len(areas) == 1 and contributors else None,
            "area_name": ", ".join(areas) or None, "status": status,
        })
    return result
