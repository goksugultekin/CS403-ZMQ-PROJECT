
from dataclasses import dataclass
from kafka import KafkaConsumer

@dataclass
class KafkaRecovery:
    brokers: str
    topic: str
    group_id: str


    def replay_all(self):
        consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=self.brokers.split(","),
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            group_id=self.group_id,
            value_deserializer=lambda b: b,
            key_deserializer=lambda b: b.decode("utf-8") if b else "",
        )
        for msg in consumer:
            yield msg.key, msg.value
