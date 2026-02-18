# phase1_messaging/message.py
"""
Vector Clock based messaging for Phase 1.

Each message carries:
  - sender:       who sent it
  - event_type:   what happened (send, internal, etc.)
  - payload:      user text
  - vector_clock: {node_id: counter} dict
"""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class VectorClock:
    """
    Vector Clock implementation.

    Each node maintains a dict {node_id: counter}.
    On local event:  increment own entry.
    On receive:      merge (pointwise max) then increment own entry.
    """
    clock: Dict[str, int] = field(default_factory=dict)

    def tick(self, node_id: str):
        """Increment this node's entry (local event)."""
        self.clock[node_id] = self.clock.get(node_id, 0) + 1

    def merge(self, other: Dict[str, int]):
        """Merge with another vector clock (pointwise max)."""
        for node_id, counter in other.items():
            self.clock[node_id] = max(self.clock.get(node_id, 0), counter)

    def merge_and_tick(self, other: Dict[str, int], node_id: str):
        """Merge then increment own entry (on receive)."""
        self.merge(other)
        self.tick(node_id)

    def snapshot(self) -> Dict[str, int]:
        """Return a copy of the current clock."""
        return dict(self.clock)

    def happens_before(self, other: Dict[str, int]) -> bool:
        """Check if self happened before other (self < other)."""
        all_keys = set(self.clock.keys()) | set(other.keys())
        at_least_one_less = False
        for k in all_keys:
            mine = self.clock.get(k, 0)
            theirs = other.get(k, 0)
            if mine > theirs:
                return False
            if mine < theirs:
                at_least_one_less = True
        return at_least_one_less

    def is_concurrent(self, other: Dict[str, int]) -> bool:
        """Check if self and other are concurrent (neither < the other)."""
        other_vc = VectorClock(clock=dict(other))
        return not self.happens_before(other) and not other_vc.happens_before(self.clock)

    def __repr__(self):
        items = ", ".join(f"{k}:{v}" for k, v in sorted(self.clock.items()))
        return f"VC({items})"


@dataclass
class Message:
    sender: str
    event_type: str       # "send", "internal", "receive"
    payload: str
    vector_clock: Dict[str, int]
