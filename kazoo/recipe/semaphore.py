"""Zookeeper Semaphore"""

import uuid

from kazoo.retry import ForceRetryError
from kazoo.exceptions import CancelledError
from kazoo.exceptions import NoNodeException
import sys

class Semaphore(object):
    """Kazoo Basic Semaphore

    """
    _NODE_NAME = '__semaphore__'

    def __init__(self, client, path, maxLocks, identifier=None):
        """Create a Kazoo Semaphore

        """
        self.client = client
        self.path = path
        self.maxLocks = maxLocks

        # some data is written to the node. this can be queried via
        # contenders() to see who is contending for the lock
        self.data = str(identifier or "")

        self.wake_event = client.handler.event_object()

        # props to Netflix Curator for this trick. It is possible for our
        # create request to succeed on the server, but for a failure to
        # prevent us from getting back the full path name. We prefix our
        # lock name with a uuid and can check for its presence on retry.
        self.prefix = uuid.uuid4().hex + self._NODE_NAME
        self.create_path = self.path + "/" + self.prefix

        self.create_tried = False
        self.is_acquired = False
        self.assured_path = False
        self.cancelled = False

    def cancel(self):
        """Cancel a pending lock acquire"""
        self.cancelled = True
        self.wake_event.set()

    def acquire(self):
        pass

    def release(self):
        pass

    def _inner_acquire(self):
        self.wake_event.clear()

        # make sure our election parent node exists
        if not self.assured_path:
            self.client.ensure_path(self.path)

        node = None
        if self.create_tried:
            node = self._find_node()
        else:
            self.create_tried = True

        if not node:
            node = self.client.create(self.create_path, self.data,
                ephemeral=True, sequence=True)
            # strip off path to node
            node = node[len(self.path) + 1:]

        self.node = node

        while True:

            # bail out with an exception if cancellation has been requested
            if self.cancelled:
                raise CancelledError()

            children = self._get_sorted_children()

            try:
                our_index = children.index(node)
            except ValueError:
                # somehow we aren't in the children -- probably we are
                # recovering from a session failure and our ephemeral
                # node was removed
                raise ForceRetryError()

            if our_index < self.maxLocks:
                return True

            # otherwise we are in the mix. watch predecessor and bide our time
            predecessor = self.path + "/" + children[our_index - 1]
            if self.client.exists(predecessor, self._watch_predecessor):
                self.wake_event.wait()

    def _watch_predecessor(self, event):
        self.wake_event.set()

    def _get_sorted_children(self):
        children = self.client.get_children(self.path)

        # can't just sort directly: the node names are prefixed by uuids
        lockname = self._NODE_NAME
        children.sort(key=lambda c: c[c.find(lockname) + len(lockname):])
        return children

    def _find_node(self):
        children = self.client.get_children(self.path)
        for child in children:
            if child.startswith(self.prefix):
                return child
        return None

    def _best_effort_cleanup(self):
        try:
            node = self._find_node()
            if node:
                self.client.delete(self.path + "/" + node)
        except Exception:
            pass

    def release(self):
        """Release the mutex immediately"""
        return self.client.retry(self._inner_release)

    def _inner_release(self):
        if not self.is_acquired:
            return False

        self.client.delete(self.path + "/" + self.node)

        self.is_acquired = False
        self.node = None

        return True

    def contenders(self):
        """Return an ordered list of the current contenders for the lock

        .. note::

            If the contenders did not set an identifier, it will appear
            as a blank string.

        """
        # make sure our election parent node exists
        if not self.assured_path:
            self.client.ensure_path(self.path)

        children = self._get_sorted_children()

        contenders = []
        for child in children:
            try:
                data, stat = self.client.get(self.path + "/" + child)
                contenders.append(data)
            except NoNodeException:
                pass
        return contenders

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()    