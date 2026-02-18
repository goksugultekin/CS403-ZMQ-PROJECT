# phase2_crdt_move/crdt/move_crdt.py
from dataclasses import dataclass
from typing import Any, List, Optional, Set, Tuple, Iterable, Dict
import threading

# move_time: (lamport_counter:int, replica_id:str)
Timestamp = Tuple[int, str]

@dataclass(frozen=True)
class Move:
    move_time: Timestamp
    move_parent: Any
    move_meta: Any
    move_child: Any

@dataclass(frozen=True)
class LogMove:
    log_time: Timestamp
    old_parent: Optional[Tuple[Any, Any]]
    new_parent: Any
    log_meta: Any
    log_child: Any

State = Tuple[List[LogMove], Set[Tuple[Any, Any, Any]]]

def get_parent(tree: Set[Tuple[Any, Any, Any]], child: Any) -> Optional[Tuple[Any, Any]]:
    matches = [(p, m) for (p, m, c) in tree if c == child]
    if len(matches) == 1:
        return matches[0]
    return None

def _children_map(tree: Set[Tuple[Any, Any, Any]]) -> Dict[Any, List[Tuple[Any, Any]]]:
    d: Dict[Any, List[Tuple[Any, Any]]] = {}
    for p, m, c in tree:
        d.setdefault(p, []).append((m, c))
    return d

def ancestor(tree: Set[Tuple[Any, Any, Any]], parent: Any, child: Any) -> bool:
    if parent == child:
        return False
    children = _children_map(tree)
    stack, seen = [parent], set()
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        if node == child:
            return True
        for _, c in children.get(node, []):
            if c not in seen:
                stack.append(c)
    return False

def do_op(op: Move, tree: Set[Tuple[Any, Any, Any]]):
    if op is None:
        raise ValueError("Move operation cannot be None")

    t, newp, m, c = op.move_time, op.move_parent, op.move_meta, op.move_child

    if c is None:
        raise ValueError("Child node cannot be None")
    if newp is None:
        raise ValueError("New parent cannot be None")

    oldp = get_parent(tree, c)
    log = LogMove(t, oldp, newp, m, c)

    # self-parent invalid
    if c == newp:
        return log, set(tree)

    # remove old edge for c, add new edge
    temp_tree = {(p2, m2, c2) for (p2, m2, c2) in tree if c2 != c}
    temp_tree.add((newp, m, c))

    # cycle check
    if ancestor(temp_tree, c, newp):
        return log, set(tree)

    return log, temp_tree

def undo_op(logop: LogMove, tree: Set[Tuple[Any, Any, Any]]):
    if logop is None:
        raise ValueError("LogMove operation cannot be None")

    c = logop.log_child
    if c is None:
        raise ValueError("Child node in log cannot be None")

    base = {(p2, m2, c2) for (p2, m2, c2) in tree if c2 != c}

    if logop.old_parent is None:
        return base

    oldp, oldm = logop.old_parent
    base.add((oldp, oldm, c))
    return base

def apply_op(op: Move, state: State) -> State:
    """
    Apply a move to the CRDT state using undo-redo.

    The log is kept sorted by timestamp (newest first).
    When a new op arrives:
      1. Undo all log entries with timestamp > op.move_time
      2. Apply the new op via do_op
      3. Redo the undone entries in timestamp order (oldest first)

    This ensures convergence regardless of delivery order.
    """
    log, tree = state

    # 1. Find the insertion point: undo entries newer than op
    undone = []
    remaining_log = list(log)
    working_tree = set(tree)

    while remaining_log and remaining_log[0].log_time > op.move_time:
        newest = remaining_log.pop(0)
        working_tree = undo_op(newest, working_tree)
        undone.append(newest)

    # 2. Apply the new op
    new_log_entry, working_tree = do_op(op, working_tree)

    # Build the new log with the new entry inserted
    new_log = [new_log_entry] + remaining_log

    # 3. Redo the undone entries (they were newest, so redo oldest-first)
    for old_entry in reversed(undone):
        # Reconstruct the Move from the log entry
        redo_move = Move(
            move_time=old_entry.log_time,
            move_parent=old_entry.new_parent,
            move_meta=old_entry.log_meta,
            move_child=old_entry.log_child,
        )
        redo_log_entry, working_tree = do_op(redo_move, working_tree)
        new_log.insert(0, redo_log_entry)

    return (new_log, working_tree)


def apply_ops(ops: Iterable[Move]) -> State:
    state: State = ([], set())
    for oper in ops:
        state = apply_op(oper, state)
    return state

def pretty_tree(tree: Set[Tuple[Any, Any, Any]]) -> str:
    children = _children_map(tree)
    roots = {p for (p, m, c) in tree} - {c for (p, m, c) in tree}
    if not roots:
        roots = {p for (p, m, c) in tree}
    lines = []
    def dfs(node: Any, depth: int):
        lines.append("  " * depth + f"- {node}")
        for m, c in sorted(children.get(node, []), key=lambda x: str(x)):
            lines.append("  " * (depth + 1) + f"{m} -> {c}")
            dfs(c, depth + 2)
    for r in sorted(roots, key=lambda x: str(x)):
        dfs(r, 0)
    return "\n".join(lines)

class ThreadSafeState:
    def __init__(self, initial_tree: Optional[Set[Tuple[Any, Any, Any]]] = None):
        if initial_tree is None:
            initial_tree = set()
        self._state: State = ([], set(initial_tree))
        self._lock = threading.Lock()

    def apply(self, op: Move) -> None:
        if op is None:
            raise ValueError("Move operation cannot be None")
        with self._lock:
            self._state = apply_op(op, self._state)

    def snapshot(self) -> State:
        with self._lock:
            log, tree = self._state
            return (list(log), set(tree))

    def tree(self) -> Set[Tuple[Any, Any, Any]]:
        with self._lock:
            return set(self._state[1])

    def log(self) -> List[LogMove]:
        with self._lock:
            return list(self._state[0])

    # BONUS: log büyümesini sınırlamak istersen
    def truncate_log(self, max_entries: int = 1000) -> None:
        with self._lock:
            log, tree = self._state
            if len(log) > max_entries:
                self._state = (log[:max_entries], tree)
