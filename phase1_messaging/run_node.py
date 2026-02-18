# phase1_messaging/run_node.py
"""
Phase 1 CLI – Vector Clock based messaging.

Commands:
  send <text>     – broadcast a message to all peers
  event <text>    – generate a local (internal) event
  log             – show all events with vector clocks
  clock           – show current vector clock
  exit            – stop the node
"""
import json
import sys
from node import Phase1Node


def main():
    if len(sys.argv) != 2:
        print("usage: python run_node.py config_node_X.json")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        cfg = json.load(f)

    my_id = cfg["my_id"]
    peers = cfg["peers"]

    me = next(p for p in peers if p["id"] == my_id)
    others = [p for p in peers if p["id"] != my_id]

    node = Phase1Node(
        my_id=my_id,
        my_pub_port=me["pub_port"],
        peers=others,
    )

    print(f"Node: {my_id}")
    print("Commands:")
    print("  send <text>   – broadcast message")
    print("  event <text>  – local event (no broadcast)")
    print("  log           – show event log")
    print("  clock         – show vector clock")
    print("  exit          – stop\n")

    while True:
        try:
            line = input(f"{my_id}> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0]

        if cmd == "exit":
            break
        elif cmd == "send" and len(parts) == 2:
            node.send(parts[1])
        elif cmd == "event":
            desc = parts[1] if len(parts) == 2 else "internal"
            node.internal_event(desc)
        elif cmd == "log":
            node.show_log()
        elif cmd == "clock":
            node.show_clock()
        else:
            print("Commands: send <text>, event <text>, log, clock, exit")

    node.close()
    print(f"[{my_id}] Stopped.")


if __name__ == "__main__":
    main()
