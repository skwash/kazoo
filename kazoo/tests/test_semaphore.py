import uuid
import threading
import zookeeper
from nose.tools import eq_

from kazoo.exceptions import CancelledError
from kazoo.testing import KazooTestCase
from kazoo.tests.util import wait
import time

from threading import BoundedSemaphore

class KazooSemaphoreTests(KazooTestCase):
    def setUp(self):
        super(KazooSemaphoreTests, self).setUp()
        self.sempath = "/" + uuid.uuid4().hex

        self.condition = threading.Condition()
        self.released = threading.Event()
        self.active_threads = []
        self.cancelled_threads = []

        self.semaphore = None

    def _thread_semaphore_acquire_til_event(self, name, semaphore, event):
        try:
            with semaphore:
                with self.condition:
                    self.active_threads.append(name)
                    self.condition.notify_all()

                event.wait()

                with self.condition:
                    self.active_threads.remove(name)
                    self.condition.notify_all()
            self.released.set()

        except CancelledError:
            with self.condition:
                self.cancelled_threads.append(name)
                self.condition.notify_all()

    def test_semaphore_one(self):

        semaphore_name = uuid.uuid4().hex
        semaphore = self.client.Semaphore(self.sempath, 1, semaphore_name)
        event = threading.Event()
        
        thread = threading.Thread(target=self._thread_semaphore_acquire_til_event,
            args=(semaphore_name, semaphore, event))
        thread.start()

        semaphore2_name = uuid.uuid4().hex
        anothersemaphore = self.client.Semaphore(self.sempath, 1, semaphore2_name)

        with self.condition:
            while semaphore_name not in self.active_threads:
                self.condition.wait()

        eq_(self.active_threads, [semaphore_name])
        eq_(anothersemaphore.contenders(), [semaphore_name])

        # release the lock
        event.set()

        with self.condition:
            while semaphore_name in self.active_threads:
                self.condition.wait()
        self.released.wait()

        thread.join()

    def test_semaphore(self):
        
        num_threads = 15
        max_locks = 5
        threads = []
        names = ["contender" + str(i) for i in range(num_threads)]

        contender_bits = {}
        
        #e = threading.Event()
        for name in names:
            e = threading.Event()

            s = self.client.Semaphore(self.sempath, max_locks, name)
            t = threading.Thread(target=self._thread_semaphore_acquire_til_event,
                args=(name, s, e))
            contender_bits[name] = (t, e)
            threads.append(t)

        semaphore_name = uuid.uuid4().hex
        semaphore = self.client.Semaphore(self.sempath, max_locks, semaphore_name)

        i=0
        for t in threads:
            i+=1
            t.start()
            # Make sure each thread starts in order.
            wait(lambda: len(semaphore.contenders()) == i)

        # Make sure all threads are up and running.
        wait(lambda: len(semaphore.contenders()) == num_threads)
        contenders = semaphore.contenders()

        # Set each thread's event one at a time, making sure we roll through contenders in order.
        # It might be a good idea to set the events randomly and check those results just to verify
        # that we don't have weird in-order only issues.
        for contender in contenders:
            thread, event = contender_bits[contender]

            eq_(self.active_threads, semaphore.contenders()[:max_locks])
            event.set()
            wait(lambda: contender not in self.active_threads)

            thread.join()
