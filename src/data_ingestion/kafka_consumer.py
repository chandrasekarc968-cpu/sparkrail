"""
Kafka consumer module for real-time railway events streaming.
"""
from confluent_kafka import Consumer

class RailwayEventConsumer:
    def __init__(self, config):
        self.config = config
        self.consumer = Consumer({
            'bootstrap.servers': config['kafka']['bootstrap_servers'],
            'group.id': 'railway_block_planning',
            'auto.offset.reset': 'earliest'
        })
        self.topic = config['kafka']['topic']

    def consume_events(self):
        self.consumer.subscribe([self.topic])
        while True:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue
            
            yield msg.value()

    def close(self):
        self.consumer.close()
