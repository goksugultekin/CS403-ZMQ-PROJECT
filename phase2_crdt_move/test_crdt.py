"""
Phase 2 CRDT Move – unit tests for cycle detection and LWW correctness.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from phase2_crdt_move.crdt.move_crdt import (
    Move, LogMove, ThreadSafeState,
    do_op, apply_op, apply_ops, ancestor, get_parent, pretty_tree,
)


def make_move(lamport, replica, parent, child, meta="edge"):
    return Move(
        move_time=(lamport, replica),
        move_parent=parent,
        move_meta=meta,
        move_child=child,
    )


# ─── Helper ──────────────────────────────────────────────
def tree_edges(tree):
    """Return set of (parent, child) for readability."""
    return {(p, c) for p, _, c in tree}


def has_edge(tree, parent, child):
    return any(p == parent and c == child for p, _, c in tree)


# ═══════════════════════════════════════════════════════════
# TEST 1: Basic move
# ═══════════════════════════════════════════════════════════
def test_basic_move():
    print("TEST 1: Basic move")
    # Initial tree:  root -> A -> B
    tree = {("root", "e1", "A"), ("A", "e2", "B")}

    # Move B under root
    m = make_move(1, "r1", "root", "B")
    log, new_tree = do_op(m, tree)

    assert has_edge(new_tree, "root", "B"), f"B should be under root, got {tree_edges(new_tree)}"
    assert has_edge(new_tree, "root", "A"), "A should still be under root"
    assert not has_edge(new_tree, "A", "B"), "B should no longer be under A"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 2: Self-parent rejection
# ═══════════════════════════════════════════════════════════
def test_self_parent():
    print("TEST 2: Self-parent rejection")
    tree = {("root", "e1", "A")}

    # Try to move A under itself
    m = make_move(1, "r1", "A", "A")
    log, new_tree = do_op(m, tree)

    assert new_tree == tree, f"Tree should not change on self-parent, got {tree_edges(new_tree)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 3: Direct cycle – move parent under its own child
# ═══════════════════════════════════════════════════════════
def test_direct_cycle():
    print("TEST 3: Direct cycle – move parent under its child")
    # root -> A -> B
    tree = {("root", "e1", "A"), ("A", "e2", "B")}

    # Move A under B  (would create B -> A -> B cycle)
    m = make_move(1, "r1", "B", "A")
    log, new_tree = do_op(m, tree)

    assert new_tree == tree, (
        f"Cycle should be rejected. Expected {tree_edges(tree)}, got {tree_edges(new_tree)}"
    )
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 4: Indirect cycle – longer chain
# ═══════════════════════════════════════════════════════════
def test_indirect_cycle():
    print("TEST 4: Indirect cycle – root->A->B->C, move A under C")
    tree = {("root", "e1", "A"), ("A", "e2", "B"), ("B", "e3", "C")}

    # Move A under C  (would create C -> A -> B -> C)
    m = make_move(1, "r1", "C", "A")
    log, new_tree = do_op(m, tree)

    assert new_tree == tree, (
        f"Indirect cycle should be rejected. Expected {tree_edges(tree)}, got {tree_edges(new_tree)}"
    )
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 5: Valid move after cycle rejection
# ═══════════════════════════════════════════════════════════
def test_valid_after_cycle():
    print("TEST 5: Valid move after a rejected cycle")
    # root -> A -> B -> C
    tree = {("root", "e1", "A"), ("A", "e2", "B"), ("B", "e3", "C")}

    # First: rejected cycle (A under C)
    m1 = make_move(1, "r1", "C", "A")
    _, tree = do_op(m1, tree)

    # Then: valid move (C under root)
    m2 = make_move(2, "r1", "root", "C")
    _, tree = do_op(m2, tree)

    assert has_edge(tree, "root", "C"), f"C should be under root, got {tree_edges(tree)}"
    assert has_edge(tree, "root", "A"), "A should still be under root"
    assert has_edge(tree, "A", "B"), "B should still be under A"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 6: ThreadSafeState – sequential applies
# ═══════════════════════════════════════════════════════════
def test_thread_safe_sequential():
    print("TEST 6: ThreadSafeState sequential applies")
    state = ThreadSafeState({("root", "e1", "A"), ("root", "e2", "B")})

    # Move B under A  (valid)
    state.apply(make_move(1, "r1", "A", "B"))
    t = state.tree()
    assert has_edge(t, "A", "B"), f"B should be under A, got {tree_edges(t)}"

    # Move A under B  (cycle – should be rejected)
    state.apply(make_move(2, "r1", "B", "A"))
    t = state.tree()
    assert has_edge(t, "root", "A"), f"A should still be under root (cycle rejected), got {tree_edges(t)}"
    assert has_edge(t, "A", "B"), f"B should still be under A, got {tree_edges(t)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 7: LWW – later timestamp wins
# ═══════════════════════════════════════════════════════════
def test_lww_later_wins():
    print("TEST 7: LWW – later timestamp should win")
    state = ThreadSafeState({("root", "e1", "A"), ("root", "e2", "B"), ("root", "e3", "C")})

    # r1 moves A under B at time 1
    state.apply(make_move(1, "r1", "B", "A"))
    t = state.tree()
    assert has_edge(t, "B", "A"), f"A should be under B, got {tree_edges(t)}"

    # r2 moves A under C at time 2 (later – should win)
    state.apply(make_move(2, "r2", "C", "A"))
    t = state.tree()
    assert has_edge(t, "C", "A"), f"A should be under C (later ts wins), got {tree_edges(t)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 8: LWW – earlier timestamp should lose
# ═══════════════════════════════════════════════════════════
def test_lww_earlier_loses():
    print("TEST 8: LWW – earlier timestamp should be ignored")
    state = ThreadSafeState({("root", "e1", "A"), ("root", "e2", "B"), ("root", "e3", "C")})

    # r2 moves A under C at time 2
    state.apply(make_move(2, "r2", "C", "A"))
    t = state.tree()
    assert has_edge(t, "C", "A"), f"A should be under C, got {tree_edges(t)}"

    # r1 moves A under B at time 1 (earlier – should be ignored)
    state.apply(make_move(1, "r1", "B", "A"))
    t = state.tree()
    assert has_edge(t, "C", "A"), f"A should STILL be under C (earlier ts ignored), got {tree_edges(t)}"
    assert not has_edge(t, "B", "A"), f"A should NOT be under B, got {tree_edges(t)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 9: Concurrent moves – same child, different parents
# ═══════════════════════════════════════════════════════════
def test_concurrent_moves():
    print("TEST 9: Concurrent moves – both move same node")
    state = ThreadSafeState({
        ("root", "e1", "A"),
        ("root", "e2", "B"),
        ("root", "e3", "C"),
    })

    # r1 moves C under A at time 1
    state.apply(make_move(1, "r1", "A", "C"))
    # r2 moves C under B at time 2
    state.apply(make_move(2, "r2", "B", "C"))

    t = state.tree()
    assert has_edge(t, "B", "C"), f"C should be under B (higher ts), got {tree_edges(t)}"
    assert not has_edge(t, "A", "C"), f"C should NOT be under A, got {tree_edges(t)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 10: Cycle created by concurrent ops
# ═══════════════════════════════════════════════════════════
def test_concurrent_cycle():
    print("TEST 10: Concurrent ops that would create cycle")
    # root -> A -> B
    state = ThreadSafeState({("root", "e1", "A"), ("A", "e2", "B")})

    # r1: move B under root at time 1 (valid)
    state.apply(make_move(1, "r1", "root", "B"))
    t = state.tree()
    assert has_edge(t, "root", "B"), f"B should be under root, got {tree_edges(t)}"

    # r2: move A under B at time 2 (valid – no cycle, since B is now under root)
    state.apply(make_move(2, "r2", "B", "A"))
    t = state.tree()
    assert has_edge(t, "B", "A"), f"A should be under B, got {tree_edges(t)}"
    assert has_edge(t, "root", "B"), f"B should still be under root, got {tree_edges(t)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 11: Moving a new node (not yet in tree)
# ═══════════════════════════════════════════════════════════
def test_new_node():
    print("TEST 11: Adding a completely new node")
    state = ThreadSafeState({("root", "e1", "A")})

    state.apply(make_move(1, "r1", "A", "X"))
    t = state.tree()
    assert has_edge(t, "A", "X"), f"X should be under A, got {tree_edges(t)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 12: Diamond – no false-positive cycle detection
# ═══════════════════════════════════════════════════════════
def test_diamond_no_false_cycle():
    print("TEST 12: Diamond structure – no false cycle")
    # root -> A, root -> B, A -> C
    # Move C under B (should be fine – no cycle)
    tree = {("root", "e1", "A"), ("root", "e2", "B"), ("A", "e3", "C")}

    m = make_move(1, "r1", "B", "C")
    _, new_tree = do_op(m, tree)

    assert has_edge(new_tree, "B", "C"), f"C should be under B, got {tree_edges(new_tree)}"
    assert not has_edge(new_tree, "A", "C"), f"C should NOT be under A, got {tree_edges(new_tree)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 13: Out-of-order delivery – ops arrive in wrong order
# ═══════════════════════════════════════════════════════════
def test_out_of_order():
    print("TEST 13: Out-of-order delivery – later op arrives first")
    # root -> A, root -> B
    # Op1 (t=1): move A under B
    # Op2 (t=2): move A under root  (should win because higher ts)
    # But op2 arrives first, then op1

    state = ThreadSafeState({("root", "e1", "A"), ("root", "e2", "B")})

    # op2 arrives first (t=2)
    state.apply(make_move(2, "r2", "root", "A"))
    t = state.tree()
    assert has_edge(t, "root", "A"), f"A should be under root, got {tree_edges(t)}"

    # op1 arrives later (t=1) – should be rejected (earlier ts)
    state.apply(make_move(1, "r1", "B", "A"))
    t = state.tree()
    assert has_edge(t, "root", "A"), f"A should STILL be under root (op1 is older), got {tree_edges(t)}"
    assert not has_edge(t, "B", "A"), f"A should NOT be under B, got {tree_edges(t)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 14: Multiple moves on different children
# ═══════════════════════════════════════════════════════════
def test_multiple_children():
    print("TEST 14: Multiple moves on different children")
    state = ThreadSafeState({
        ("root", "e1", "A"),
        ("root", "e2", "B"),
        ("root", "e3", "C"),
        ("root", "e4", "D"),
    })

    state.apply(make_move(1, "r1", "A", "B"))  # B under A
    state.apply(make_move(2, "r1", "B", "C"))  # C under B
    state.apply(make_move(3, "r1", "C", "D"))  # D under C

    t = state.tree()
    # Should be: root -> A -> B -> C -> D
    assert has_edge(t, "root", "A"), f"got {tree_edges(t)}"
    assert has_edge(t, "A", "B"), f"got {tree_edges(t)}"
    assert has_edge(t, "B", "C"), f"got {tree_edges(t)}"
    assert has_edge(t, "C", "D"), f"got {tree_edges(t)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 15: Deep cycle rejection – move root-child under leaf
# ═══════════════════════════════════════════════════════════
def test_deep_chain_cycle():
    print("TEST 15: Deep chain – root->A->B->C->D, move A under D")
    state = ThreadSafeState({
        ("root", "e1", "A"),
        ("A", "e2", "B"),
        ("B", "e3", "C"),
        ("C", "e4", "D"),
    })

    # Move A under D – would create D->A->B->C->D cycle
    state.apply(make_move(1, "r1", "D", "A"))
    t = state.tree()

    # A should still be under root (cycle rejected)
    assert has_edge(t, "root", "A"), f"A should still be under root, got {tree_edges(t)}"
    assert has_edge(t, "A", "B"), f"B should still be under A, got {tree_edges(t)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 16: Interleaved concurrent ops from two replicas
# ═══════════════════════════════════════════════════════════
def test_interleaved_concurrent():
    print("TEST 16: Interleaved concurrent ops – two replicas")
    # root -> A, root -> B, root -> C
    # r1: move B under A (t=1)
    # r2: move C under B (t=2)
    # r1: move C under A (t=3) – should override r2's move

    state = ThreadSafeState({
        ("root", "e1", "A"),
        ("root", "e2", "B"),
        ("root", "e3", "C"),
    })

    state.apply(make_move(1, "r1", "A", "B"))  # B under A
    t = state.tree()
    assert has_edge(t, "A", "B"), f"B should be under A, got {tree_edges(t)}"

    state.apply(make_move(2, "r2", "B", "C"))  # C under B
    t = state.tree()
    assert has_edge(t, "B", "C"), f"C should be under B, got {tree_edges(t)}"

    state.apply(make_move(3, "r1", "A", "C"))  # C under A (overrides)
    t = state.tree()
    assert has_edge(t, "A", "C"), f"C should now be under A, got {tree_edges(t)}"
    assert not has_edge(t, "B", "C"), f"C should NOT be under B anymore, got {tree_edges(t)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 17: Cycle after rearrangement
# ═══════════════════════════════════════════════════════════
def test_cycle_after_rearrangement():
    print("TEST 17: Cycle created by sequence of valid moves")
    # root -> A, root -> B
    state = ThreadSafeState({("root", "e1", "A"), ("root", "e2", "B")})

    # Move B under A (valid) -> root -> A -> B
    state.apply(make_move(1, "r1", "A", "B"))
    t = state.tree()
    assert has_edge(t, "A", "B"), f"got {tree_edges(t)}"

    # Move A under B (cycle!) -> would create B -> A -> B
    state.apply(make_move(2, "r2", "B", "A"))
    t = state.tree()
    assert has_edge(t, "root", "A"), f"A should still be under root (cycle rejected), got {tree_edges(t)}"
    assert has_edge(t, "A", "B"), f"B should still be under A, got {tree_edges(t)}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 18: apply_ops convergence – different order same result
# ═══════════════════════════════════════════════════════════
def test_apply_ops_convergence():
    print("TEST 18: apply_ops – same ops, different order should converge")
    m1 = make_move(1, "r1", "root", "A")
    m2 = make_move(2, "r2", "root", "B")
    m3 = make_move(3, "r1", "A", "B")

    state1 = apply_ops([m1, m2, m3])
    state2 = apply_ops([m2, m1, m3])
    state3 = apply_ops([m3, m1, m2])

    t1 = state1[1]
    t2 = state2[1]
    t3 = state3[1]

    assert t1 == t2 == t3, (
        f"All orderings should converge!\n"
        f"  order [m1,m2,m3]: {tree_edges(t1)}\n"
        f"  order [m2,m1,m3]: {tree_edges(t2)}\n"
        f"  order [m3,m1,m2]: {tree_edges(t3)}"
    )
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 19: Convergence with 4 ops, all permutations
# ═══════════════════════════════════════════════════════════
def test_full_convergence():
    print("TEST 19: Full convergence – 4 ops, all 24 permutations")
    from itertools import permutations

    ops = [
        make_move(1, "r1", "root", "A"),
        make_move(2, "r2", "root", "B"),
        make_move(3, "r1", "A", "C"),
        make_move(4, "r2", "B", "D"),
    ]

    results = []
    for perm in permutations(ops):
        state = apply_ops(perm)
        results.append(state[1])

    first = results[0]
    for i, t in enumerate(results):
        assert t == first, (
            f"Permutation {i} diverged!\n"
            f"  expected: {tree_edges(first)}\n"
            f"  got:      {tree_edges(t)}"
        )
    print(f"  All {len(results)} permutations converged to: {tree_edges(first)}")
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 20: Convergence with conflicting moves on same child
# ═══════════════════════════════════════════════════════════
def test_convergence_conflict():
    print("TEST 20: Convergence – conflicting moves on same child")
    from itertools import permutations

    # All three replicas move node X to different parents
    ops = [
        make_move(1, "r1", "root", "A"),
        make_move(2, "r2", "root", "B"),
        make_move(3, "r3", "root", "X"),
        make_move(4, "r1", "A", "X"),   # r1 wants X under A
        make_move(5, "r2", "B", "X"),   # r2 wants X under B (wins – higher ts)
    ]

    results = []
    for perm in permutations(ops):
        state = apply_ops(perm)
        results.append(state[1])

    first = results[0]
    for i, t in enumerate(results):
        assert t == first, (
            f"Permutation {i} diverged!\n"
            f"  expected: {tree_edges(first)}\n"
            f"  got:      {tree_edges(t)}"
        )

    assert has_edge(first, "B", "X"), f"X should be under B (highest ts), got {tree_edges(first)}"
    print(f"  All {len(results)} permutations converged. X is under B (correct).")
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# RUN ALL TESTS
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    tests = [
        test_basic_move,
        test_self_parent,
        test_direct_cycle,
        test_indirect_cycle,
        test_valid_after_cycle,
        test_thread_safe_sequential,
        test_lww_later_wins,
        test_lww_earlier_loses,
        test_concurrent_moves,
        test_concurrent_cycle,
        test_new_node,
        test_diamond_no_false_cycle,
        test_out_of_order,
        test_multiple_children,
        test_deep_chain_cycle,
        test_interleaved_concurrent,
        test_cycle_after_rearrangement,
        test_apply_ops_convergence,
        test_full_convergence,
        test_convergence_conflict,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}\n")
            failed += 1

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed == 0:
        print("All tests passed!")
    else:
        print("Some tests FAILED!")
