# phase1_messaging/run_node.py
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
        peers=others
    )

    print(f"My ID: {my_id}")
    print("Type a message and press enter.\n")

    try:
        while True:
            line = input("> ")
            if not line:
                continue
            node.send(line)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()

if __name__ == "__main__":
    main()
