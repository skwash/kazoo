"""Kazoo testing harnesses"""
import atexit
import logging
import os
import uuid
import threading
import unittest

from kazoo.client import KazooClient
from kazoo.protocol.states import (
    KazooState
)
from kazoo.testing.common import ZookeeperCluster

log = logging.getLogger(__name__)

CLUSTER = None


def get_global_cluster():
    global CLUSTER
    if CLUSTER is None:
        ZK_HOME = os.environ.get("ZOOKEEPER_PATH")
        assert ZK_HOME, (
            "ZOOKEEPER_PATH environment variable must be defined.\n "
            "For deb package installations this is /usr/share/java")

        CLUSTER = ZookeeperCluster(ZK_HOME)
        atexit.register(lambda cluster: cluster.terminate(), CLUSTER)
    return CLUSTER


class KazooTestHarness(object):
    """Harness for testing code that uses Kazoo

    This object can be used directly or as a mixin. It supports starting
    and stopping a complete ZooKeeper cluster locally and provides an
    API for simulating errors and expiring sessions.

    Example::

        class MyTestCase(unittest.TestCase, KazooTestHarness):
            def setUp(self):
                self.setup_zookeeper()

                # additional test setup

            def tearDown(self):
                self.teardown_zookeeper()

            def test_something(self):
                something_that_needs_a_kazoo_client(self.client)

            def test_something_else(self):
                something_that_needs_zk_servers(self.servers)

    """

    def __init__(self):
        self.client = None

    @property
    def cluster(self):
        return get_global_cluster()

    @property
    def servers(self):
        return ",".join([s.address for s in self.cluster])

    def _get_nonchroot_client(self):
        return KazooClient(self.servers)

    def _get_client(self, **kwargs):
        return KazooClient(self.hosts, **kwargs)

    def expire_session(self, client_id=None):
        """Force ZK to expire a client session

        :param client_id: id of client to expire. If unspecified, the id of
                          self.client will be used.

        """
        client_id = client_id or self.client.client_id

        lost = threading.Event()

        def watch_loss(state):
            if state == KazooState.LOST:
                lost.set()
                return True

        self.client.add_listener(watch_loss)

        client = KazooClient(self.hosts, client_id=client_id, timeout=0.8)
        client.start()
        client.stop()
        self.client.get_async('/')
        lost.wait()

    def setup_zookeeper(self):
        """Create a ZK cluster and chrooted :class:`KazooClient`

        The cluster will only be created on the first invocation and won't be
        fully torn down until exit.
        """
        if not self.cluster[0].running:
            self.cluster.start()
        namespace = "/kazootests" + uuid.uuid4().hex
        self.hosts = self.servers + namespace

        self.client = self._get_client(timeout=0.8)
        self.client.start()
        self.client.ensure_path("/")

    def teardown_zookeeper(self):
        """Clean up any ZNodes created during the test
        """
        if not self.cluster[0].running:
            self.cluster.start()

        if self.client.connected:
            self.client.delete('/', recursive=True)
            self.client.stop()
            self.client.stop()
            del self.client
        else:
            client = self._get_client()
            client.start()
            client.delete('/', recursive=True)
            client.stop()
            del client

    def add_errors(self, errors):
        self.client.zookeeper = ZookeeperErrors(errors, self.client.handler)


class KazooTestCase(unittest.TestCase, KazooTestHarness):
    def setUp(self):
        self.setup_zookeeper()

    def tearDown(self):
        self.teardown_zookeeper()
