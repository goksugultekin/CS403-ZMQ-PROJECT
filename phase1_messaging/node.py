# phase1_messaging/node.py
import json
import threading
import time
import zmq
from message import Message

class Phase1Node:
    def __init__(self, my_id, my_pub_port, peers):
        self.my_id = my_id
        self.counter = 0

        self.ctx = zmq.Context.instance()

        # PUB   
        self.pub = self.ctx.socket(zmq.PUB)
        self.pub.bind(f"tcp://*:{my_pub_port}")

        # SUB
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.setsockopt_string(zmq.SUBSCRIBE, "MSG")

        for p in peers:
            self.sub.connect(f"tcp://{p['ip']}:{p['pub_port']}")

        self.running = True

        self.sub_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.sub_thread.start()

        
        time.sleep(0.3)

    def _recv_loop(self):
        while self.running:
            try:
                topic, raw = self.sub.recv_multipart()
                msg = json.loads(raw.decode())
                print(f"\n[RX] from={msg['sender']} cnt={msg['counter']} payload='{msg['payload']}'")
            except zmq.ZMQError:
                break

    def send(self, payload: str):
        self.counter += 1
        msg = Message(
            sender=self.my_id,
            counter=self.counter,
            payload=payload
        )
        data = json.dumps(msg.__dict__).encode()
        self.pub.send_multipart([b"MSG", data])
        print(f"[TX] {payload}")

    def close(self):
        self.running = False
        self.pub.close(0)
        self.sub.close(0)
        self.ctx.term()
