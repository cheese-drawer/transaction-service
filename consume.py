import gzip
import json
from typing import Any
from test.integration.helpers.connection import connect, Channel

connection, channel = connect(
    'localhost',
    8672,
    'test',
    'pass')


def handler(ch: Channel, method: Any, _: Any, body: bytes) -> None:
    print('Message received:')
    print(json.loads(gzip.decompress(body).decode('UTF8')))
    ch.basic_ack(delivery_tag=method.delivery_tag)


channel.queue_declare(queue='logging', durable=True)
channel.basic_consume(queue='logging', on_message_callback=handler)

try:
    print('Starting consumer...')
    channel.start_consuming()
except KeyboardInterrupt:
    channel.stop_consuming()
    print('\nStopping consumer...')
finally:
    channel.close()
    connection.close()
    print('Connection closed.')
