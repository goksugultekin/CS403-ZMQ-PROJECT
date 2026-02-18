"""
Phase 3 Distributed File System Node

Leaderless replicated file system using ZeroMQ PUB/SUB
Kafka for durability, and LWW conflict resolution

Reuses KafkaLog and KafkaRecovery from Phase 2
"""

import threading
import time
import zmq
from typing import List

from phase2_crdt_move.kafka_io.kafka_log import KafkaLog
from phase2_crdt_move.kafka_io.recovery import KafkaRecovery

from phase3_distributed_state.distributed_fs.proto.fs_pb2 import (
    FsOperation,
    CREATE,
    WRITE,
    DELETE,
    RENAME,
)
from phase3_distributed_state.distributed_fs.fs_state import (
    ThreadSafeFileState,
)


def op_to_bytes(op: FsOperation) -> bytes:
    return op.SerializeToString()


def bytes_to_op(raw: bytes) -> FsOperation:
    op = FsOperation()
    op.ParseFromString(raw)
    return op


class Peer:
    def __init__(self, id: str, ip: str, pub_port: int):
        self.id = id
        self.ip = ip
        self.pub_port = pub_port


class Phase3FileSystemNode:
    """
    Distributed file system node

    All nodes are equal (leaderless). Any node can create, write,
    delete, or rename files. Operations are broadcast via ZMQ PUB/SUB
    and persisted to Kafka for crash recovery
    """

    def __init__(
        self,
        my_id: str,
        pub_port: int,
        peers: List[Peer],
        kafka_brokers: str,
        kafka_topic: str,
        storage_dir: str,
    ):
        self.my_id = my_id
        self.peers = peers
        self.lamport = 0

        # file system state
        self.state = ThreadSafeFileState(storage_dir)

        # kafka
        self.kafka_log = KafkaLog(kafka_brokers, kafka_topic)
        self.kafka_recovery = KafkaRecovery(
            kafka_brokers, kafka_topic,
            group_id=f"fs-replay-{my_id}",
        )

        # ZMQ PUB/SUB
        self.ctx = zmq.Context.instance()

        self.pub = self.ctx.socket(zmq.PUB)
        self.pub.bind(f"tcp://*:{pub_port}")

        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.setsockopt_string(zmq.SUBSCRIBE, "")
        for p in peers:
            self.sub.connect(f"tcp://{p.ip}:{p.pub_port}")

        self.running = False

        # let ZMQ connections settle
        time.sleep(0.3)

    # ── Recovery 

    def recover_from_kafka(self, max_msgs: int = 10_000):
        count = 0
        for _, raw in self.kafka_recovery.replay_all():
            op = bytes_to_op(raw)
            self._update_lamport(op.lamport)
            self._apply_op(op)
            count += 1
            if count >= max_msgs:
                break
        print(f"[{self.my_id}] Recovered {count} ops from Kafka")

    # ── Start / Stop 

    def start(self):
        self.running = True
        threading.Thread(
            target=self._recv_loop, daemon=True
        ).start()

    def stop(self):
        self.running = False
        self.pub.close(0)
        self.sub.close(0)
        self.ctx.term()

    # ── Receive loop 

    def _recv_loop(self):
        while self.running:
            try:
                raw = self.sub.recv()
                op = bytes_to_op(raw)
                if op.sender_id == self.my_id:
                    continue
                self._update_lamport(op.lamport)
                self._apply_op(op)
                self._print_remote_op(op)
            except zmq.ZMQError:
                break

    # ── Local operations 

    def create_file(self, filename: str, content: str):
        self._tick_lamport()
        op = FsOperation(
            type=CREATE,
            sender_id=self.my_id,
            lamport=self.lamport,
            filename=filename,
            content=content,
        )
        self._apply_op(op)
        self._broadcast_and_log(op)
        print(f"[{self.my_id}] Created '{filename}'")

    def write_file(self, filename: str, content: str):
        self._tick_lamport()
        op = FsOperation(
            type=WRITE,
            sender_id=self.my_id,
            lamport=self.lamport,
            filename=filename,
            content=content,
        )
        self._apply_op(op)
        self._broadcast_and_log(op)
        print(f"[{self.my_id}] Wrote '{filename}'")

    def delete_file(self, filename: str):
        self._tick_lamport()
        op = FsOperation(
            type=DELETE,
            sender_id=self.my_id,
            lamport=self.lamport,
            filename=filename,
        )
        self._apply_op(op)
        self._broadcast_and_log(op)
        print(f"[{self.my_id}] Deleted '{filename}'")

    def rename_file(self, old_name: str, new_name: str):
        self._tick_lamport()
        op = FsOperation(
            type=RENAME,
            sender_id=self.my_id,
            lamport=self.lamport,
            filename=old_name,
            new_filename=new_name,
        )
        self._apply_op(op)
        self._broadcast_and_log(op)
        print(f"[{self.my_id}] Renamed '{old_name}' -> '{new_name}'")

    def list_files(self):
        files = self.state.list_files()
        if not files:
            print("  (empty)")
        else:
            for line in files:
                print(line)

    def read_file(self, filename: str):
        content = self.state.read_file(filename)
        if content is None:
            print(f"  File '{filename}' not found")
        else:
            print(f"  {content}")

    # ── Internal 

    def _apply_op(self, op: FsOperation):
        ts = (op.lamport, op.sender_id)
        if op.type == CREATE:
            self.state.apply_create(op.filename, op.content, ts)
        elif op.type == WRITE:
            self.state.apply_write(op.filename, op.content, ts)
        elif op.type == DELETE:
            self.state.apply_delete(op.filename, ts)
        elif op.type == RENAME:
            self.state.apply_rename(
                op.filename, op.new_filename, ts
            )

    def _broadcast_and_log(self, op: FsOperation):
        payload = op_to_bytes(op)
        self.kafka_log.append(self.my_id, payload)
        self.pub.send(payload)

    def _print_remote_op(self, op: FsOperation):
        op_names = {CREATE: "CREATE", WRITE: "WRITE",
                    DELETE: "DELETE", RENAME: "RENAME"}
        name = op_names.get(op.type, "?")
        detail = op.filename
        if op.type == RENAME:
            detail = f"{op.filename} -> {op.new_filename}"
        print(
            f"[{self.my_id}] recv {name} '{detail}' "
            f"from={op.sender_id} ts={op.lamport}"
        )

    def _tick_lamport(self):
        self.lamport += 1

    def _update_lamport(self, other: int):
        self.lamport = max(self.lamport, other) + 1
