import sys
import traceback
import os
os.environ['TZ'] = 'UTC'

import argparse

import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("pika").setLevel(logging.WARNING)
logging.getLogger("docker").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("ampq").setLevel(logging.WARNING)

root_logger = logging.getLogger()

# Create handlers
c_handler = logging.StreamHandler()
f_handler = logging.FileHandler('/tmp/unpack_controller_logs.log')
# c_handler.setLevel(logging.DEBUG)
# f_handler.setLevel(logging.DEBUG)

# Create formatters and add it to handlers
c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
f_format = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

# Add handlers to the logger
root_logger.addHandler(c_handler)
root_logger.addHandler(f_handler)

logger = logging.getLogger(__name__)


def handle_excepthook(exctype, value, tb):
    uncaught_logger = logging.getLogger('uncaught')
    message = ''.join(traceback.format_exception(exctype, value, tb))
    uncaught_logger.critical(message)

sys.excepthook = handle_excepthook


def main():
    parser = argparse.ArgumentParser(description='Start an unpack queue...')
    parser.add_argument(
        'action',
        choices=[
            'api-server',
            'queue-manager',
            'queue-fetcher-worker',
            'queue-broadcast-worker',
        ],
        help='Unpack queue name'
    )
    parser.add_argument('-q', help="Queue Name")

    args = parser.parse_args()

    if args.action == 'api-server':
        import unpack.api.server
        unpack.api.server.main()

    elif args.action == 'queue-manager':
        import unpack.queues.manager
        unpack.queues.manager.main(args.q)

    elif args.action == 'queue-fetcher-worker':
        import unpack.queues.workers.fetcher
        unpack.queues.workers.fetcher.main(args.q)

    elif args.action == 'queue-broadcast-worker':
        import unpack.queues.workers.broadcaster
        unpack.queues.workers.broadcaster.main(args.q)

if __name__ == '__main__':
    main()
