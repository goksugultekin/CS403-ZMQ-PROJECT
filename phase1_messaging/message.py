# phase1_messaging/message.py
from dataclasses import dataclass

@dataclass
class Message:
    sender: str
    counter: int
    payload: str
