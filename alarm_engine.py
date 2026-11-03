"""Pure manual alarm state machine."""

from dataclasses import asdict, dataclass, replace
from datetime import datetime

from .const import SERVICES, STATES


@dataclass(frozen=True)
class AlarmState:
    """One manual house-test alarm; no multiple-alarm arbitration."""

    state: str = "idle"
    test_count: int = 0
    last_triggered: str | None = None
    last_changed: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AlarmState":
        if not isinstance(data, dict) or set(data) != set(asdict(cls())):
            raise ValueError("Invalid stored alarm fields")
        if data["state"] not in STATES:
            raise ValueError("Invalid stored alarm state")
        if type(data["test_count"]) is not int or data["test_count"] < 0:
            raise ValueError("Invalid stored test counter")
        for key in ("last_triggered", "last_changed"):
            value = data[key]
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError("Invalid stored timestamp")
                if datetime.fromisoformat(value).tzinfo is None:
                    raise ValueError("Stored timestamps must include timezone")
        return cls(**data)


def transition(current: AlarmState, action: str, now: str) -> AlarmState:
    """Trigger reactivates an acknowledged alarm; ack/reset are idempotent."""
    if action not in SERVICES:
        raise ValueError("Unknown alarm action")
    if action == "trigger_test":
        return replace(
            current, state="active", test_count=current.test_count + 1,
            last_triggered=now, last_changed=now,
        )
    target = "acknowledged" if action == "acknowledge" else "idle"
    if current.state == target or (action == "acknowledge" and current.state == "idle"):
        return current
    return replace(current, state=target, last_changed=now)
