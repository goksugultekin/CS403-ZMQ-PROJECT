# Phase 1 – ZeroMQ Message Passing

## Overview

In this phase, you will build a **multi-process messaging system** using
**ZeroMQ PUB/SUB sockets**.

Each process runs independently and communicates **only by sending messages**.
There is **no shared memory**, **no global clock**, and **no consistency guarantee**.

This phase focuses purely on **distributed communication fundamentals**.

---

## Learning Objectives

After completing this phase, you should be able to:

- Run multiple distributed processes on the same machine
- Use ZeroMQ PUB/SUB sockets for message passing
- Serialize and deserialize messages
- Understand why PUB/SUB is **not** a connection-oriented protocol
- Observe and explain the **slow-join problem**
- Explain how message passing differs from TCP sockets

---
