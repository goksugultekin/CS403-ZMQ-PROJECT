"""
Phase 1 – Vector Clock unit tests.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from message import VectorClock


# ═══════════════════════════════════════════════════════════
# TEST 1: Tick increments own entry
# ═══════════════════════════════════════════════════════════
def test_tick():
    print("TEST 1: Tick increments own entry")
    vc = VectorClock()
    vc.tick("A")
    assert vc.clock == {"A": 1}, f"Expected A:1, got {vc.clock}"
    vc.tick("A")
    assert vc.clock == {"A": 2}, f"Expected A:2, got {vc.clock}"
    vc.tick("B")
    assert vc.clock == {"A": 2, "B": 1}, f"got {vc.clock}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 2: Merge takes pointwise max
# ═══════════════════════════════════════════════════════════
def test_merge():
    print("TEST 2: Merge takes pointwise max")
    vc = VectorClock(clock={"A": 2, "B": 1})
    vc.merge({"A": 1, "B": 3, "C": 1})
    assert vc.clock == {"A": 2, "B": 3, "C": 1}, f"got {vc.clock}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 3: Merge and tick (receive event)
# ═══════════════════════════════════════════════════════════
def test_merge_and_tick():
    print("TEST 3: Merge and tick (receive event)")
    vc = VectorClock(clock={"A": 2})
    vc.merge_and_tick({"A": 1, "B": 3}, "A")
    # merge: A=max(2,1)=2, B=max(0,3)=3
    # tick A: A=3
    assert vc.clock == {"A": 3, "B": 3}, f"got {vc.clock}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 4: Happens-before (causal ordering)
# ═══════════════════════════════════════════════════════════
def test_happens_before():
    print("TEST 4: Happens-before relation")
    vc1 = VectorClock(clock={"A": 1, "B": 0})
    vc2_dict = {"A": 2, "B": 1}

    # vc1 < vc2 (all entries <=, at least one <)
    assert vc1.happens_before(vc2_dict) is True, "vc1 should happen before vc2"

    # vc2 does NOT happen before vc1
    vc2 = VectorClock(clock={"A": 2, "B": 1})
    assert vc2.happens_before({"A": 1, "B": 0}) is False, "vc2 should NOT happen before vc1"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 5: Concurrent events
# ═══════════════════════════════════════════════════════════
def test_concurrent():
    print("TEST 5: Concurrent events detection")
    # A did 2 events, B did 0
    vc1 = VectorClock(clock={"A": 2, "B": 0})
    # A did 0 events, B did 3
    vc2_dict = {"A": 0, "B": 3}

    # Neither happens before the other
    assert vc1.happens_before(vc2_dict) is False
    vc2 = VectorClock(clock=vc2_dict)
    assert vc2.happens_before(vc1.clock) is False
    assert vc1.is_concurrent(vc2_dict) is True
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 6: Equal clocks – not happens-before, not concurrent
# ═══════════════════════════════════════════════════════════
def test_equal_clocks():
    print("TEST 6: Equal clocks")
    vc = VectorClock(clock={"A": 1, "B": 1})
    same = {"A": 1, "B": 1}
    assert vc.happens_before(same) is False, "Equal clocks: not happens-before"
    # is_concurrent checks neither <, but equal means both <=, not strictly <
    # so happens_before returns False for both directions, is_concurrent returns True
    # Actually: happens_before requires at_least_one_less, equal has none, so False
    # And the reverse is also False. So is_concurrent should be True.
    # But conceptually equal clocks represent the same logical time.
    # Our implementation will say concurrent=True since neither is strictly before.
    assert vc.is_concurrent(same) is True, "Equal clocks are neither before nor after"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 7: Three-node scenario
# ═══════════════════════════════════════════════════════════
def test_three_nodes():
    print("TEST 7: Three-node event scenario")

    # Simulate: A sends, B receives, B does internal, C sends, B receives from C
    vc_a = VectorClock()
    vc_b = VectorClock()
    vc_c = VectorClock()

    # A sends event
    vc_a.tick("A")  # A={A:1}
    msg_a = vc_a.snapshot()
    assert msg_a == {"A": 1}, f"got {msg_a}"

    # B receives from A
    vc_b.merge_and_tick(msg_a, "B")  # B={A:1, B:1}
    assert vc_b.clock == {"A": 1, "B": 1}, f"got {vc_b.clock}"

    # B does internal event
    vc_b.tick("B")  # B={A:1, B:2}
    assert vc_b.clock == {"A": 1, "B": 2}, f"got {vc_b.clock}"

    # C sends (independently)
    vc_c.tick("C")  # C={C:1}
    msg_c = vc_c.snapshot()

    # B receives from C
    vc_b.merge_and_tick(msg_c, "B")  # B={A:1, B:3, C:1}
    assert vc_b.clock == {"A": 1, "B": 3, "C": 1}, f"got {vc_b.clock}"

    # A and C are concurrent (A didn't see C, C didn't see A)
    assert vc_a.is_concurrent(msg_c) is True, "A and C should be concurrent"

    # A happens before B's current state
    assert vc_a.happens_before(vc_b.clock) is True, "A should happen before B"

    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 8: Snapshot returns independent copy
# ═══════════════════════════════════════════════════════════
def test_snapshot():
    print("TEST 8: Snapshot returns independent copy")
    vc = VectorClock(clock={"A": 1})
    snap = vc.snapshot()
    vc.tick("A")
    assert snap == {"A": 1}, f"Snapshot should not change, got {snap}"
    assert vc.clock == {"A": 2}, f"Original should be updated, got {vc.clock}"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 9: Causal chain – A -> B -> C
# ═══════════════════════════════════════════════════════════
def test_causal_chain():
    print("TEST 9: Causal chain A -> B -> C")
    vc_a = VectorClock()
    vc_b = VectorClock()
    vc_c = VectorClock()

    # A sends
    vc_a.tick("A")
    snap_a = vc_a.snapshot()

    # B receives from A, then sends
    vc_b.merge_and_tick(snap_a, "B")
    vc_b.tick("B")  # send event
    snap_b = vc_b.snapshot()

    # C receives from B
    vc_c.merge_and_tick(snap_b, "C")

    # A -> B -> C  (transitive)
    assert vc_a.happens_before(vc_b.clock), "A should happen before B"
    assert vc_b.happens_before(vc_c.clock), "B should happen before C"
    assert vc_a.happens_before(vc_c.clock), "A should happen before C (transitivity)"
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# TEST 10: Missing keys treated as zero
# ═══════════════════════════════════════════════════════════
def test_missing_keys():
    print("TEST 10: Missing keys treated as zero")
    vc = VectorClock(clock={"A": 1})
    # Compare with vc that has B entry but not A
    other = {"B": 1}
    # A:1 vs A:0 -> mine > theirs for A, so not happens_before
    assert vc.happens_before(other) is False
    # B:0 vs B:1 -> theirs > mine for B, but A:1 > A:0, so concurrent
    assert vc.is_concurrent(other) is True
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════
# RUN ALL TESTS
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    tests = [
        test_tick,
        test_merge,
        test_merge_and_tick,
        test_happens_before,
        test_concurrent,
        test_equal_clocks,
        test_three_nodes,
        test_snapshot,
        test_causal_chain,
        test_missing_keys,
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
