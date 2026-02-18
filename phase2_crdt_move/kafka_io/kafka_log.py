
from dataclasses import dataclass
from kafka import KafkaProducer

@dataclass
class KafkaLog:
    brokers: str
    topic: str


    def __post_init__(self) -> None:
        self.producer = KafkaProducer(
            bootstrap_servers=self.brokers.split(","),
            acks="all",   
            retries=5,
            value_serializer=lambda b: b,   # bytes
            key_serializer=lambda s: s.encode("utf-8"),
        )



    def append(self, key: str, value_bytes: bytes) -> None:
        fut = self.producer.send(self.topic, key=key, value=value_bytes)
        fut.get(timeout=10)  
