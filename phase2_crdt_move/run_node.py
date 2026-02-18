import json
import sys
import threading

from phase2_crdt_move.node import Phase2MoveNode, Peer


def main():
    if len(sys.argv) != 2:
        print("usage: python3 run_node.py config.json")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        cfg = json.load(f)

    my_id = cfg["id"]
    pub_port = cfg["pub_port"]
    peers = [Peer(**p) for p in cfg["peers"]]
    kafka_brokers = cfg["kafka"]["brokers"]
    kafka_topic = cfg["kafka"]["topic"]

    node = Phase2MoveNode(
        my_id,
        pub_port,
        peers,
        kafka_brokers,
        kafka_topic,
    )


    def recovery():
        print(f"[{my_id}] recovering from kafka...")
        node.recover_from_kafka()
        print(f"[{my_id}] recovery finished.")

    threading.Thread(target=recovery, daemon=True).start()


    threading.Thread(target=node.start, daemon=True).start()

  
    print("commands:")
    print("  move <new_parent> <meta> <child>")
    print("  show")
    print("  exit")

    while True:
        try:
            cmd = input(f"{my_id}> ").strip()
        except EOFError:
            break

        if not cmd:
            continue

        if cmd == "exit":
            break

        if cmd == "show":
            node.print_tree()
            continue

        parts = cmd.split()
        if parts[0] == "move" and len(parts) == 4:
            node.local_move(parts[1], parts[2], parts[3])
        else:
            print("unknown command")

    node.stop()
    print(f"[{my_id}] stopped.")


if __name__ == "__main__":
    main()
