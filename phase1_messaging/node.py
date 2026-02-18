# phase1_messaging/node.py
"""
Phase 1 Node with Vector Clock.

Each node:
  - Maintains a VectorClock
  - Generates local events (send, internal) that tick the clock
  - Receives remote events and merges clocks
  - Logs all events with their vector clock state
"""
import json
import threading
import time
import zmq
from message import Message, VectorClock


class Phase1Node:
    def __init__(self, my_id, my_pub_port, peers):
        self.my_id = my_id
        self.vc = VectorClock()
        self.event_log = []       # list of (event_type, payload, vc_snapshot)
        self._lock = threading.Lock()

        self.ctx = zmq.Context.instance()

        # PUB socket
        self.pub = self.ctx.socket(zmq.PUB)
        self.pub.bind(f"tcp://*:{my_pub_port}")

        # SUB socket
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.setsockopt_string(zmq.SUBSCRIBE, "MSG")
        for p in peers:
            self.sub.connect(f"tcp://{p['ip']}:{p['pub_port']}")

        self.running = True
        self.sub_thread = threading.Thread(
            target=self._recv_loop, daemon=True
        )
        self.sub_thread.start()

        time.sleep(0.3)

    # ── Send event ─────────────────────────────────────
    def send(self, payload: str):
        """Generate a send event: tick VC, broadcast message."""
        with self._lock:
            self.vc.tick(self.my_id)
            snap = self.vc.snapshot()
            self.event_log.append(("send", payload, snap))

        msg = Message(
            sender=self.my_id,
            event_type="send",
            payload=payload,
            vector_clock=snap,
        )
        data = json.dumps(msg.__dict__).encode()
        self.pub.send_multipart([b"MSG", data])
        print(f"[SEND] {payload}  vc={self.vc}")

    # ── Internal event ─────────────────────────────────
    def internal_event(self, description: str = "internal"):
        """Generate a local event: tick VC, no broadcast."""
        with self._lock:
            self.vc.tick(self.my_id)
            snap = self.vc.snapshot()
            self.event_log.append(("internal", description, snap))
        print(f"[EVENT] {description}  vc={self.vc}")

    # ── Receive loop ───────────────────────────────────
    def _recv_loop(self):
        while self.running:
            try:
                topic, raw = self.sub.recv_multipart()
                msg_dict = json.loads(raw.decode())

                sender = msg_dict["sender"]
                payload = msg_dict["payload"]
                remote_vc = msg_dict["vector_clock"]

                with self._lock:
                    # Check causality before merge
                    relation = self._causality(remote_vc)

                    # Merge and tick
                    self.vc.merge_and_tick(remote_vc, self.my_id)
                    snap = self.vc.snapshot()
                    self.event_log.append(("receive", payload, snap))

                print(
                    f"[RECV] from={sender} payload='{payload}' "
                    f"remote_vc={remote_vc} relation={relation} "
                    f"merged_vc={self.vc}"
                )
            except zmq.ZMQError:
                break

    # ── Causality check ────────────────────────────────
    def _causality(self, remote_vc: dict) -> str:
        """Determine causal relation between local VC and remote VC."""
        if self.vc.happens_before(remote_vc):
            return "BEFORE (local -> remote)"
        remote = VectorClock(clock=dict(remote_vc))
        if remote.happens_before(self.vc.clock):
            return "AFTER (remote -> local)"
        return "CONCURRENT"

    # ── Show event log ─────────────────────────────────
    def show_log(self):
        """Print all recorded events with their vector clocks."""
        with self._lock:
            if not self.event_log:
                print("  (no events)")
                return
            for i, (etype, payload, vc) in enumerate(self.event_log):
                vc_str = ", ".join(
                    f"{k}:{v}" for k, v in sorted(vc.items())
                )
                print(f"  {i+1}. [{etype:8s}] {payload:20s} VC({vc_str})")

    # ── Show current VC ────────────────────────────────
    def show_clock(self):
        """Print the current vector clock state."""
        with self._lock:
            print(f"  {self.vc}")

    # ── Cleanup ────────────────────────────────────────
    def close(self):
        self.running = False
        self.pub.close(0)
        self.sub.close(0)
        self.ctx.term()
