"""
Phase 3 Distributed File System -- CLI entry point

Usage:
    python -m phase3_distributed_state.distributed_fs.run_node config_node_A.json
"""

import json
import sys
import threading

from phase3_distributed_state.distributed_fs.node import (
    Phase3FileSystemNode,
    Peer,
)


def main():
    if len(sys.argv) != 2:
        print("usage: python run_node.py <config.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        cfg = json.load(f)

    my_id = cfg["id"]
    pub_port = cfg["pub_port"]
    peers = [Peer(**p) for p in cfg["peers"]]
    kafka_brokers = cfg["kafka"]["brokers"]
    kafka_topic = cfg["kafka"]["topic"]
    storage_dir = cfg["storage_dir"]

    node = Phase3FileSystemNode(
        my_id, pub_port, peers,
        kafka_brokers, kafka_topic, storage_dir,
    )

    # recovery from Kafka
    def recovery():
        print(f"[{my_id}] Recovering from Kafka...")
        node.recover_from_kafka()
        print(f"[{my_id}] Recovery finished.")

    threading.Thread(target=recovery, daemon=True).start()

    # start node
    threading.Thread(target=node.start, daemon=True).start()

    print("Commands:")
    print("  create <filename> <content...>")
    print("  write  <filename> <content...>")
    print("  delete <filename>")
    print("  rename <old> <new>")
    print("  ls")
    print("  cat <filename>")
    print("  exit")

    while True:
        try:
            cmd = input(f"{my_id}> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue

        parts = cmd.split()
        action = parts[0]

        if action == "exit":
            break
        elif action == "ls":
            node.list_files()
        elif action == "cat" and len(parts) >= 2:
            node.read_file(parts[1])
        elif action == "create" and len(parts) >= 3:
            filename = parts[1]
            content = " ".join(parts[2:])
            node.create_file(filename, content)
        elif action == "write" and len(parts) >= 3:
            filename = parts[1]
            content = " ".join(parts[2:])
            node.write_file(filename, content)
        elif action == "delete" and len(parts) >= 2:
            node.delete_file(parts[1])
        elif action == "rename" and len(parts) >= 3:
            node.rename_file(parts[1], parts[2])
        else:
            print("Unknown command. Try: create, write, "
                  "delete, rename, ls, cat, exit")

    node.stop()
    print(f"[{my_id}] Stopped.")


if __name__ == "__main__":
    main()
