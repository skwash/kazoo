import uuid
import threading
import zookeeper
from nose.tools import eq_

from kazoo.exceptions import CancelledError
from kazoo.testing import KazooTestCase
from kazoo.testing import ZooError
from kazoo.tests.util import wait


class KazooSemaphoreTests(KazooTestCase):
    def setUp(self):
        super(KazooSemaphoreTests, self).setUp()
        self.semaphorepath = "/" + uuid.uuid4().hex

        self.condition = threading.Condition()
        self.released = threading.Event()
        self.active_thread = None
        self.cancelled_threads = []

    def _thread_semaphore_acquire_til_event(self, name, semaphore, event):
        try:
            with semaphore:
                with self.condition:
                    #eq_(self.active_thread, None)
                    self.active_thread = name
                    self.condition.notify_all()

                event.wait()

                with self.condition:
                    #eq_(self.active_thread, name)
                    self.active_thread = None
                    self.condition.notify_all()
            self.released.set()
        except CancelledError:
            with self.condition:
                self.cancelled_threads.append(name)
                self.condition.notify_all()

    def test_semaphore_one(self):
        semaphore_name = uuid.uuid4().hex
        semaphore = self.client.Lock(self.semaphorepath, semaphore_name)
        event = threading.Event()

        thread = threading.Thread(target=self._thread_semaphore_acquire_til_event,
            args=(semaphore_name, semaphore, event))
        thread.start()

        semaphore2_name = uuid.uuid4().hex
        anothersemaphore = self.client.Lock(self.semaphorepath, semaphore2_name)

        # wait for any contender to show up on the semaphore
        wait(anothersemaphore.contenders)
        eq_(anothersemaphore.contenders(), [semaphore_name])

        with self.condition:
            while self.active_thread != semaphore_name:
                self.condition.wait()

        # release the semaphore
        event.set()

        with self.condition:
            while self.active_thread:
                self.condition.wait()
        self.released.wait()

    def test_semaphore(self):
        threads = []
        names = ["contender" + str(i) for i in range(5)]

        contender_bits = {}

        for name in names:
            e = threading.Event()

            l = self.client.Semaphore(self.semaphorepath, 1, name)
            t = threading.Thread(target=self._thread_semaphore_acquire_til_event,
                args=(name, l, e))
            contender_bits[name] = (t, e)
            threads.append(t)

        # acquire the semaphore ourselves first to make the others line up
        semaphore = self.client.Semaphore(self.semaphorepath, 1, "test")
        semaphore.acquire()

        for t in threads:
            t.start()

        # wait for everyone to line up on the semaphore
        wait(lambda: len(semaphore.contenders()) == 6)
        contenders = semaphore.contenders()

        eq_(contenders[0], "test")
        contenders = contenders[1:]
        remaining = list(contenders)

        # release the semaphore and contenders should claim it in order
        semaphore.release()

        for contender in contenders:
            thread, event = contender_bits[contender]

            with self.condition:
                while not self.active_thread:
                    self.condition.wait()
                eq_(self.active_thread, contender)

            eq_(semaphore.contenders(), remaining)
            remaining = remaining[1:]

            event.set()

            with self.condition:
                while self.active_thread:
                    self.condition.wait()
            thread.join()

    def test_semaphore_fail_first_call(self):
        self.add_errors(dict(
            acreate=[True,  # This is our semaphore node create
                     ZooError('completion', zookeeper.CONNECTIONLOSS, True)
                    ]
        ))

        event1 = threading.Event()
        semaphore1 = self.client.Semaphore(self.semaphorepath, 1, "one")
        thread1 = threading.Thread(target=self._thread_semaphore_acquire_til_event,
            args=("one", semaphore1, event1))
        thread1.start()

        # wait for this thread to acquire the semaphore
        with self.condition:
            if not self.active_thread:
                self.condition.wait(5)
                eq_(self.active_thread, "one")
        eq_(semaphore1.contenders(), ["one"])
        event1.set()
        thread1.join()

    def test_semaphore_cancel(self):
        event1 = threading.Event()
        semaphore1 = self.client.Semaphore(self.semaphorepath, 1, "one")
        thread1 = threading.Thread(target=self._thread_semaphore_acquire_til_event,
            args=("one", semaphore1, event1))
        thread1.start()

        # wait for this thread to acquire the semaphore
        with self.condition:
            if not self.active_thread:
                self.condition.wait(5)
                eq_(self.active_thread, "one")

        client2 = self._get_client()
        client2.start()
        event2 = threading.Event()
        semaphore2 = client2.Semaphore(self.semaphorepath, 1, "two")
        thread2 = threading.Thread(target=self._thread_semaphore_acquire_til_event,
            args=("two", semaphore2, event2))
        thread2.start()

        # this one should block in acquire. check that it is a contender
        wait(lambda: len(semaphore2.contenders()) > 1)
        eq_(semaphore2.contenders(), ["one", "two"])

        semaphore2.cancel()
        with self.condition:
            if not "two" in self.cancelled_threads:
                self.condition.wait()
                assert "two" in self.cancelled_threads

        eq_(semaphore2.contenders(), ["one"])

        thread2.join()
        event1.set()
        thread1.join()
        client2.stop()

