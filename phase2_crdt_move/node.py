import threading
import time
import zmq
from typing import List

from phase2_crdt_move.proto.move_pb2 import MoveEvent
from phase2_crdt_move.crdt.move_crdt import Move, ThreadSafeState
from phase2_crdt_move.kafka_io.kafka_log import KafkaLog
from phase2_crdt_move.kafka_io.recovery import KafkaRecovery



def move_to_bytes(move):
    lamport, rid = move.move_time
    ev = MoveEvent(
        lamport=lamport,
        replica_id=rid,
        new_parent=str(move.move_parent),
        meta=str(move.move_meta),
        child=str(move.move_child),
    )
    return ev.SerializeToString()


def bytes_to_move(raw: bytes):
    ev = MoveEvent()
    ev.ParseFromString(raw)
    return Move(
        move_time=(ev.lamport, ev.replica_id),
        move_parent=ev.new_parent,
        move_meta=ev.meta,
        move_child=ev.child,
    )


class Peer:
    def __init__(self, id: str, ip: str, pub_port: int):
        self.id = id
        self.ip = ip
        self.pub_port = pub_port


class Phase2MoveNode:
    def __init__(
        self,
        my_id: str,
        pub_port: int,
        peers: List[Peer],
        kafka_brokers: str,
        kafka_topic: str,
    ):
        self.my_id = my_id
        self.peers = peers

        #lamport clock
        self.lamport = 0

        #cRDT state
        self.state = ThreadSafeState()

        #kafka
        self.kafka_log = KafkaLog(kafka_brokers, kafka_topic)
        self.kafka_recovery = KafkaRecovery(
            kafka_brokers,
            kafka_topic,
            group_id=f"replay-{my_id}",
        )

        #ZeroMQ
        self.ctx = zmq.Context.instance()

        #PUB socket
        self.pub = self.ctx.socket(zmq.PUB)
        self.pub.bind(f"tcp://*:{pub_port}")

        #SUB socket
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.setsockopt_string(zmq.SUBSCRIBE, "")

        for p in peers:
            self.sub.connect(f"tcp://{p.ip}:{p.pub_port}")

        self.running = False
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)

        #give ZMQ time to connect
        time.sleep(0.3)


    #recovery
    def recover_from_kafka(self, max_msgs: int = 10_000) -> None:
        count = 0
        for _, raw in self.kafka_recovery.replay_all():
            move = bytes_to_move(raw)
            self._update_lamport(move.move_time[0])
            self.state.apply(move)
            count += 1
            if count >= max_msgs:
                break

    #runtime
    def start(self) -> None:
        self.running = True
        self.recv_thread.start()

    def stop(self) -> None:
        self.running = False
        self.pub.close(0)
        self.sub.close(0)
        self.ctx.term()


    #local operations
    def local_move(self, new_parent, meta, child) -> None:
        self._tick_lamport()

        move = Move(
            move_time=(self.lamport, self.my_id),
            move_parent=new_parent,
            move_meta=meta,
            move_child=child,
        )

        payload = move_to_bytes(move)

        # durability
        self.kafka_log.append(self.my_id, payload)

        # replication
        self.pub.send(payload)

        # local apply
        self.state.apply(move)

        print(f"[{self.my_id}] local move applied")


    #receiving
    def _recv_loop(self) -> None:
        while self.running:
            try:
                raw = self.sub.recv()
                move = bytes_to_move(raw)
                self._on_remote_move(move)
            except zmq.ZMQError:
                break

    def _on_remote_move(self, move: Move) -> None:
        incoming_lamport, sender = move.move_time

        #lamport update rule
        self.lamport = max(self.lamport, incoming_lamport) + 1

        self.state.apply(move)

        print(
            f"[{self.my_id}] recv move from={sender} "
            f"ts={move.move_time}"
        )


    #lamport helpers

    def _tick_lamport(self) -> None:
        self.lamport += 1

    def _update_lamport(self, other: int) -> None:
        self.lamport = max(self.lamport, other)


    #debug helpers
    def print_tree(self) -> None:
        from phase2_crdt_move.crdt.move_crdt import pretty_tree
        print(pretty_tree(self.state.tree()))
