import os
os.environ['TZ'] = 'UTC'

from pprint import pprint
import json

import pika
from flask_socketio import SocketIO, emit

from ..helpers import UnpackHelpers
from ..types.base import TypeBase
from ..types.media import TypeMedia
from ..types.twitter import TypeTwitter

class Broadcaster:
    def __init__(self, ch, method, properties, body):
        body = json.loads(body)
        event_keys = UnpackHelpers.get_event_keys(node_url=body['origin_source_url'])
        event_data = {
            'origin_source_url': body['origin_source_url'],
            'state': body['state'],
            'source': None,
            'target': None,
        }

        if body['source_node_uuid']:
            event_data['source'] = {
                'node_url': UnpackHelpers.fetch_node_url(body['source_node_uuid']),
                'node_uuid': body['source_node_uuid'],
            }

        if body['target_node_uuid']:
            event_data['target'] = {
                'node_url': UnpackHelpers.fetch_node_url(body['target_node_uuid']),
                'node_uuid': body['target_node_uuid'],
            }

        print(event_data['target']['node_url'])
        socketio.emit(event_keys['TREE_UPDATE'], json.dumps(event_data, default=str))

def main():
    global socketio

    socketio = SocketIO(message_queue='amqp://')

    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='broadcaster', durable=True)
    print(' [*] Waiting for Broadcaster messages. To exit press CTRL+C')

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='broadcaster', on_message_callback=Broadcaster, auto_ack=True)

    channel.start_consuming()

if __name__ == '__main__':
    main()
