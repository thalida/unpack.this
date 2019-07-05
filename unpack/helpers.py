import os
os.environ['TZ'] = 'UTC'

import logging
logger = logging.getLogger(__name__)

import hashlib
import json
import uuid
import time

from redis import Redis
import docker
import psycopg2
from psycopg2.extras import RealDictCursor

r = Redis(host=os.environ['UNPACK_HOST'])


ENV_VARS = {
    'DB': {
        'HOST': 'UNPACK_HOST',
        'NAME': 'UNPACK_DB_NAME',
        'USER': 'UNPACK_DB_USER',
        'PASSWORD': 'UNPACK_DB_PASSWORD',
    }
}

class UnpackHelpers:
    DB_CREDS = {
        'host': os.getenv(ENV_VARS['DB']['HOST']),
        'dbname': os.getenv(ENV_VARS['DB']['NAME']),
        'user': os.getenv(ENV_VARS['DB']['USER']),
        'password': os.getenv(ENV_VARS['DB']['PASSWORD']),
    }

    BLANK_NODE_UUID = str(uuid.UUID(int=0))
    DEFAULT_LINK_TYPE = 0

    EVENT_NAME = {
        'LINK_FETCH_START': 'LINK_FETCH_START',
        'LINK_FETCH_SUCCESS': 'LINK_FETCH_SUCCESS',
    }

    DOCKER_CONTAINER_SETTINGS = {
        'QUEUE_MANAGER': {
            'controller_action': 'queue-manager',
            'can_create_containers': True,
        },
        'QUEUE_FETCHER_WORKER': {
            'controller_action': 'queue-fetcher-worker',
        },
        'QUEUE_BROADCAST_WORKER': {
            'controller_action': 'queue-broadcast-worker',
        },
    }
    DOCKER_CONTAINER_NAMES = { k: k for k in DOCKER_CONTAINER_SETTINGS.keys()}

    @staticmethod
    def hash_url(url):
        return hashlib.md5(str(url).encode('utf-8')).hexdigest()

    @staticmethod
    def get_url_hash(node_url):
        return UnpackHelpers.hash_url(node_url)

    @staticmethod
    def get_queue_unique_id(node_uuid):
        ms_timestamp = int(round(time.time() * 1000))
        return f'{node_uuid}:{ms_timestamp}'

    @staticmethod
    def get_queue_name(queue_type, queue_unique_id):
        return f'{queue_type}:{str(queue_unique_id)}'

    @staticmethod
    def get_queue_unique_id_from_name(queue_name):
        return queue_name.split(':', 1)[-1]

    @staticmethod
    def get_node_event_keys(node_url_hash, node_url=None, node_uuid=None):
        if node_url_hash is None:
            if node_uuid is not None:
                node_url = UnpackHelpers.fetch_node_url(node_uuid)

            if node_url is not None:
                node_url_hash = UnpackHelpers.get_url_hash(node_url)

        try:
            node_event_keys = {evt: f'{evt.lower()}:{node_url_hash}' for evt in UnpackHelpers.EVENT_NAME}
            return node_event_keys
        except Exception:
            UnpackHelpers.raise_error(
                'Error getting node_event_keys',
                node_url_hash=node_url_hash,
                node_url=node_url,
                node_uuid=node_uuid,
            )

    @staticmethod
    def start_docker_container(container_name, queue_unique_id):
        docker_client = docker.from_env()
        container_settings = UnpackHelpers.DOCKER_CONTAINER_SETTINGS[container_name]
        volumes = {}
        action = container_settings['controller_action']
        command = f"{action} -q {queue_unique_id}"

        if container_settings.get('can_create_containers', False):
            volumes.update({
                '/var/run/docker.sock': {'bind': '/var/run/docker.sock', 'mode': 'ro'},
                f'/tmp/unpack_{action}_logs.log': {'bind': '/tmp/unpack_logs.log', 'mode': 'rw'},
            })

        if os.environ['UNPACK_DEV_ENV'] == 'TRUE':
            volumes.update({
                '/Users/thalida/Repos/unpack.link/unpack': {'bind': '/unpack', 'mode': 'rw'},
                '/Users/thalida/Repos/unpack.link/controller.py': {'bind': '/controller.py', 'mode': 'rw'},
            })

        container = docker_client.containers.run(
            image="unpack_container",
            command=command,
            environment={
                'UNPACK_HOST': os.environ['UNPACK_HOST'],
                'UNPACK_DEV_ENV': os.environ['UNPACK_DEV_ENV'],
                'UNPACK_DEV_PROFILER': os.environ['UNPACK_DEV_PROFILER'],
                'UNPACK_DB_NAME': os.environ['UNPACK_DB_NAME'],
                'UNPACK_DB_USER': os.environ['UNPACK_DB_USER'],
                'UNPACK_DB_PASSWORD': os.getenv('UNPACK_DB_PASSWORD'),
            },
            volumes=volumes,
            detach=True,
        )

        return container

    @staticmethod
    def execute_sql(fetch_action, query, query_args):
        with psycopg2.connect(**UnpackHelpers.DB_CREDS) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, query_args)
                fetch_fn = getattr(cur, fetch_action)
                response = fetch_fn()

        return response

    @staticmethod
    def get_paths_for_node(node_uuid, parent_node_uuid=None, stop_node_uuid=None, stop_level=None, curr_level=0, paths=None):
        if paths is None:
            paths = []

        if (node_uuid == stop_node_uuid) or (stop_level and curr_level >= stop_level):
            return paths

        links = UnpackHelpers.fetch_links_by_source(node_uuid, parent_node_uuid=parent_node_uuid)

        if not links:
            return paths

        curr_level += 1
        for link in links:
            if link in paths:
                continue

            paths.append(link)
            paths = UnpackHelpers.get_paths_for_node(
                node_uuid=link['target_node_uuid'],
                parent_node_uuid=link['source_node_uuid'],
                stop_node_uuid=stop_node_uuid,
                curr_level=curr_level,
                stop_level=stop_level,
                paths=paths
            )

        return paths

    @staticmethod
    def check_target_node_in_tree(start_node_uuid, target_node_uuid, level, min_count=1):
        paths = UnpackHelpers.get_paths_for_node(
            node_uuid=start_node_uuid,
            stop_level=level
        )
        num_times_found = 0
        for path in paths:
            if path['target_node_uuid'] == target_node_uuid:
                num_times_found += 1

            if num_times_found >= min_count:
                return True

        return False

    @staticmethod
    def store_node(node_url):
        try:
            query = """
                    INSERT INTO node (url)
                    VALUES (%s)
                    ON CONFLICT (url) DO NOTHING
                    RETURNING uuid
                    """
            data = (node_url,)
            res = UnpackHelpers.execute_sql('fetchone', query, data)
            return res
        except Exception:
            UnpackHelpers.raise_error('Error inserting a new node: {node_url}', node_url=node_url)

    @staticmethod
    def store_node_metadata(node_uuid, node_type=None, data=None, is_error=None):
        try:
            query = """
                    INSERT INTO node_metadata (uuid, node_type, data, is_error)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (uuid) DO UPDATE
                        SET node_type = EXCLUDED.node_type,
                            data = EXCLUDED.data,
                            is_error = EXCLUDED.is_error,
                            updated_on = timezone('utc'::text, now())
                    RETURNING (uuid, node_type, data, is_error)
                    """
            query_data = (node_uuid, node_type, data, is_error)
            res = UnpackHelpers.execute_sql('fetchone', query, query_data)
            return res
        except Exception:
            UnpackHelpers.raise_error('Error inserting a metada for node: {node_uuid}', node_uuid=node_uuid)

    @staticmethod
    def store_link(source_node_uuid, target_node_uuid=None, link_type=None, weight=0):
        try:
            target_node_uuid = UnpackHelpers.BLANK_NODE_UUID if target_node_uuid is None else target_node_uuid
            link_type = UnpackHelpers.DEFAULT_LINK_TYPE if link_type is None else link_type
            query = """
                    INSERT INTO link (source_node_uuid, target_node_uuid, link_type, weight)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (source_node_uuid, target_node_uuid) DO UPDATE
                        SET link_type = EXCLUDED.link_type,
                            weight = EXCLUDED.weight,
                            updated_on = timezone('utc'::text, now())
                    RETURNING (source_node_uuid, target_node_uuid, link_type, weight)
                    """
            data = (source_node_uuid, target_node_uuid, link_type, weight)
            return UnpackHelpers.execute_sql('fetchone', query, data)
        except Exception:
            UnpackHelpers.raise_error(
                'Unpack: Error inserting a new link: {source} to {target}',
                source=source_node_uuid,
                target=target_node_uuid
            )

    @staticmethod
    def fetch_node_metadata(node_uuid, min_update_date=None):
        try:
            if min_update_date is not None:
                query = """
                        SELECT uuid, node_type, data, is_error
                        FROM node_metadata
                        WHERE uuid = %s
                        AND updated_on > %s
                        """
                query_args = (node_uuid,min_update_date,)
            else:
                query = """
                        SELECT uuid, node_type, data, is_error
                        FROM node_metadata
                        WHERE uuid = %s
                        """
                query_args = (node_uuid,)

            res = UnpackHelpers.execute_sql(
                'fetchone',
                query,
                query_args,
            )
            return res
        except Exception:
            UnpackHelpers.raise_error('Unpack: Error fetching metadta for with node_uuid: {node_uuid}', node_uuid=node_uuid)

    @staticmethod
    def fetch_links_by_source(source_node_uuid, parent_node_uuid=None):
        try:
            query = """
                    SELECT source_node_uuid, target_node_uuid, link_type, weight
                    FROM link as l
                    WHERE source_node_uuid = %s
                    AND updated_on >= (
                        SELECT max(n.updated_on)
                        FROM node_metadata as n
                        WHERE n.uuid = %s
                    )
                    ORDER BY l.updated_on DESC
                    """
            parent_node_uuid = parent_node_uuid if parent_node_uuid is not None else source_node_uuid
            query_data = (source_node_uuid,parent_node_uuid,)
            res = UnpackHelpers.execute_sql('fetchall', query, query_data)
            return res
        except Exception:
            UnpackHelpers.raise_error(
                'Unpack: Error fetching links for: {source_node_uuid}',
                source_node_uuid=source_node_uuid
            )

    @staticmethod
    def fetch_node_uuid(node_url, insert_on_new=True):
        if node_url is None:
            raise AttributeError('fetch_node_uuid_by_url requires node_url')

        cache_key = f'{node_url}:node_uuid'
        if r.exists(cache_key):
            return r.get(cache_key).decode('utf-8')

        try:
            res = UnpackHelpers.execute_sql(
                'fetchone',
                """
                SELECT uuid
                FROM node
                WHERE url = %s
                """,
                (node_url,)
            )

            if insert_on_new and res is None:
                res = UnpackHelpers.store_node(node_url)

            node_uuid = res.get('uuid')
            r.set(cache_key, node_uuid.encode('utf-8'))

            return node_uuid
        except Exception as e:
            UnpackHelpers.raise_error(
                'Unpack: Error fetching node uuid for url: {node_url}',
                node_url=node_url
            )

    @staticmethod
    def fetch_node_url(node_uuid):
        if node_uuid is None:
            raise AttributeError('fetch_node_url_by_uuid requires node_uuid')

        cache_key = f'{node_uuid}:node_url'
        if r.exists(cache_key):
            return r.get(cache_key).decode('utf-8')

        try:
            res = UnpackHelpers.execute_sql(
                'fetchone',
                """
                SELECT url
                FROM node
                WHERE uuid = %s
                """,
                (node_uuid,)
            )

            node_url = res.get('url')
            r.set(cache_key, node_url.encode('utf-8'))

            return node_url
        except Exception:
            UnpackHelpers.raise_error(
                'Unpack: Error fetching node url for uuid: {node_uuid}',
                node_uuid=node_uuid
            )

    @staticmethod
    def raise_error(msg, **kwargs):
        msg = 'something bad happended:' if msg is None else msg
        msg = msg.format(**kwargs)
        logger.exception(msg)
