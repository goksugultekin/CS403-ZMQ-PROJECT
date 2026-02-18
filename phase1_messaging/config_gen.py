# phase1_messaging/config_gen.py
import json

NODE_IDS = ["node_A", "node_B", "node_C"]
IP = "127.0.0.1"
BASE_PUB_PORT = 5550

def generate():
    peers = []
    for i, nid in enumerate(NODE_IDS):
        peers.append({
            "id": nid,
            "ip": IP,
            "pub_port": BASE_PUB_PORT + i
        })

    for nid in NODE_IDS:
        cfg = {
            "my_id": nid,
            "peers": peers
        }
        fname = f"config_{nid}.json"
        with open(fname, "w") as f:
            json.dump(cfg, f, indent=2)
        print("written:", fname)

if __name__ == "__main__":
    generate()
