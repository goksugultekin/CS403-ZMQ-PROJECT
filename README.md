# CS403 — Distributed Systems Project

## What Is This?

A hands-on distributed systems course project built in three progressive phases. Each phase introduces a new concept while building on the previous one. You start with simple message passing, add conflict-free replication, and finish with leader election.

All communication between nodes uses **ZeroMQ**. Persistent storage uses **Apache Kafka**. Messages are serialized with **Protocol Buffers** (Protobuf).

## The Three Phases

### Phase 1 — Message Passing

**Goal:** Learn how distributed processes communicate without shared memory.

- 3 nodes (A, B, C) send text messages to each other
- Uses ZeroMQ **PUB/SUB** sockets
- Messages are serialized as JSON
- No consistency guarantees — messages can be lost (slow-join problem)

```
Node A  ──PUB──>  Node B (SUB)
                  Node C (SUB)
```

### Phase 2 — CRDT with Kafka

**Goal:** Allow all nodes to apply tree-move operations independently, with eventual consistency.

- Introduces **CRDT** (Conflict-free Replicated Data Type) for a tree structure
- Every node can apply moves locally — no leader needed
- Conflicts are resolved automatically using **Last-Writer-Wins** with Lamport timestamps
- Moves are logged to **Kafka** for durability and crash recovery
- Messages are serialized with **Protobuf**

```
Node A  ──(move)──>  Local CRDT State
Node B  ──(move)──>  Local CRDT State    ← all nodes converge eventually
Node C  ──(move)──>  Local CRDT State
                         │
                    Kafka (durable log)
```

### Phase 3 — Leader Election (Bully Algorithm)

**Goal:** Replace the leaderless model with a single leader that serializes all operations.

- Only the **leader** can apply tree-move operations
- Followers send move requests to the leader
- Leader election uses the **Bully Algorithm** (highest ID wins)
- If the leader crashes, a new election happens automatically
- Uses **PUB/SUB** for broadcasts and **PUSH/PULL** for direct messages
- Kafka still provides durability and crash recovery

```
Follower A  ──MOVE_REQ──>  Leader C  ──MOVE_APPLY──>  All Nodes
Follower B  ──MOVE_REQ──>  Leader C  ──MOVE_APPLY──>  All Nodes
                               │
                          Kafka (durable log)
```

## Phase Comparison

| | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| **Communication** | PUB/SUB | PUB/SUB | PUB/SUB + PUSH/PULL |
| **Who applies operations?** | Everyone (just messages) | Everyone (CRDT) | Only the leader |
| **Conflict resolution** | None | Last-Writer-Wins (automatic) | No conflicts (single writer) |
| **Consistency** | None | Eventual | Strong |
| **Durability** | None | Kafka | Kafka |
| **Serialization** | JSON | Protobuf | Protobuf |
| **Failure handling** | None | Kafka replay | Leader election + Kafka replay |

## Project Structure

```
cs403-zmq-project/
├── phase1_messaging/                    # Phase 1: Basic message passing
│   ├── message.py                       # Message dataclass
│   ├── node.py                          # Phase1Node (PUB/SUB)
│   ├── run_node.py                      # CLI entry point
│   ├── config_node_A/B/C.json           # Node configurations
│   └── README.md
│
├── phase2_crdt_move/                    # Phase 2: CRDT + Kafka
│   ├── crdt/
│   │   └── move_crdt.py                # Move, LogMove, ThreadSafeState
│   ├── kafka_io/
│   │   ├── kafka_log.py                # KafkaLog (producer)
│   │   └── recovery.py                 # KafkaRecovery (consumer replay)
│   ├── proto/
│   │   ├── move.proto                  # Protobuf definition
│   │   └── move_pb2.py                 # Generated code
│   ├── node.py                          # Phase2MoveNode
│   ├── run_node.py                      # CLI entry point
│   └── config_node_A/B/C.json
│
├── phase3_distributed_state/            # Phase 3: Leader Election
│   └── option_b_leader_election/
│       ├── proto/
│       │   ├── election.proto           # Protobuf (6 message types)
│       │   └── election_pb2.py          # Generated code
│       ├── election.py                  # BullyElection state machine
│       ├── node.py                      # Phase3LeaderNode
│       ├── run_node.py                  # CLI entry point
│       ├── config_node_A/B/C.json
│       └── README.md
│
├── docker-compose.yml                 

└── README.md                            # This file
```

## Prerequisites

- Python 3.12+
- Docker (for Kafka and Zookeeper)
- Python packages: `pyzmq`, `kafka-python-ng`, `protobuf`

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pyzmq kafka-python-ng protobuf
```

### 2. Start Kafka (required for Phase 2 and 3)

```bash
docker-compose up -d
```

### 3. Run a phase

Each phase runs 3 nodes in 3 separate terminals. Example for Phase 3:

```bash
# Terminal 1
python -m phase3_distributed_state.option_b_leader_election.run_node \
  phase3_distributed_state/option_b_leader_election/config_node_A.json

# Terminal 2
python -m phase3_distributed_state.option_b_leader_election.run_node \
  phase3_distributed_state/option_b_leader_election/config_node_B.json

# Terminal 3
python -m phase3_distributed_state.option_b_leader_election.run_node \
  phase3_distributed_state/option_b_leader_election/config_node_C.json
```

### 4. Try commands

```
move root - child1    # Add a node to the tree
show                  # Print the tree
status                # Show role and leader info (Phase 3)
exit                  # Stop the node
```

## Key Concepts Covered

| Concept | Where It Appears |
|---|---|
| Message passing (no shared memory) | Phase 1, 2, 3 |
| ZeroMQ PUB/SUB pattern | Phase 1, 2, 3 |
| ZeroMQ PUSH/PULL pattern | Phase 3 |
| Lamport clocks | Phase 2, 3 |
| CRDT (Conflict-free Replicated Data Types) | Phase 2 |
| Last-Writer-Wins conflict resolution | Phase 2 |
| Durable event logs (Kafka) | Phase 2, 3 |
| Crash recovery via log replay | Phase 2, 3 |
| Leader election (Bully Algorithm) | Phase 3 |
| Heartbeat-based failure detection | Phase 3 |
| Strong consistency via single leader | Phase 3 |
| Protocol Buffers serialization | Phase 2, 3 |

## Port Assignments

| Node | Phase 1 (PUB) | Phase 2 (PUB) | Phase 3 (PUB) | Phase 3 (PULL) |
|------|--------------|--------------|--------------|----------------|
| A    | 5550         | 6000         | 7000         | 7100           |
| B    | 5551         | 6001         | 7001         | 7101           |
| C    | 5552         | 6002         | 7002         | 7102           |

Kafka: `localhost:9092` | Zookeeper: `localhost:2181`
