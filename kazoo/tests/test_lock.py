import uuid
import threading

from nose.tools import eq_

from kazoo.exceptions import CancelledError
from kazoo.testing import KazooTestCase
from kazoo.tests.util import wait


class KazooLockTests(KazooTestCase):
    def setUp(self):
        super(KazooLockTests, self).setUp()
        self.lockpath = "/" + uuid.uuid4().hex

        self.condition = threading.Condition()
        self.released = threading.Event()
        self.active_thread = None
        self.cancelled_threads = []

    def _thread_lock_acquire_til_event(self, name, lock, event):
        try:
            with lock:
                with self.condition:
                    eq_(self.active_thread, None)
                    self.active_thread = name
                    self.condition.notify_all()

                event.wait()

                with self.condition:
                    eq_(self.active_thread, name)
                    self.active_thread = None
                    self.condition.notify_all()
            self.released.set()
        except CancelledError:
            with self.condition:
                self.cancelled_threads.append(name)
                self.condition.notify_all()

    def test_lock_one(self):
        lock_name = uuid.uuid4().hex
        lock = self.client.Lock(self.lockpath, lock_name)
        event = threading.Event()

        thread = threading.Thread(target=self._thread_lock_acquire_til_event,
            args=(lock_name, lock, event))
        thread.start()

        lock2_name = uuid.uuid4().hex
        anotherlock = self.client.Lock(self.lockpath, lock2_name)

        # wait for any contender to show up on the lock
        wait(anotherlock.contenders)
        eq_(anotherlock.contenders(), [lock_name])

        with self.condition:
            while self.active_thread != lock_name:
                self.condition.wait()

        # release the lock
        event.set()

        with self.condition:
            while self.active_thread:
                self.condition.wait()
        self.released.wait()

    def test_lock(self):
        threads = []
        names = ["contender" + str(i) for i in range(5)]

        contender_bits = {}

        for name in names:
            e = threading.Event()

            l = self.client.Lock(self.lockpath, name)
            t = threading.Thread(target=self._thread_lock_acquire_til_event,
                args=(name, l, e))
            contender_bits[name] = (t, e)
            threads.append(t)

        # acquire the lock ourselves first to make the others line up
        lock = self.client.Lock(self.lockpath, "test")
        lock.acquire()

        for t in threads:
            t.start()

        # wait for everyone to line up on the lock
        wait(lambda: len(lock.contenders()) == 6)
        contenders = lock.contenders()

        eq_(contenders[0], "test")
        contenders = contenders[1:]
        remaining = list(contenders)

        # release the lock and contenders should claim it in order
        lock.release()

        for contender in contenders:
            thread, event = contender_bits[contender]

            with self.condition:
                while not self.active_thread:
                    self.condition.wait()
                eq_(self.active_thread, contender)

            eq_(lock.contenders(), remaining)
            remaining = remaining[1:]

            event.set()

            with self.condition:
                while self.active_thread:
                    self.condition.wait()
            thread.join()

    def test_lock_fail_first_call(self):
        event1 = threading.Event()
        lock1 = self.client.Lock(self.lockpath, "one")
        thread1 = threading.Thread(target=self._thread_lock_acquire_til_event,
            args=("one", lock1, event1))
        thread1.start()

        # wait for this thread to acquire the lock
        with self.condition:
            if not self.active_thread:
                self.condition.wait(5)
                eq_(self.active_thread, "one")
        eq_(lock1.contenders(), ["one"])
        event1.set()
        thread1.join()

    def test_lock_cancel(self):
        event1 = threading.Event()
        lock1 = self.client.Lock(self.lockpath, "one")
        thread1 = threading.Thread(target=self._thread_lock_acquire_til_event,
            args=("one", lock1, event1))
        thread1.start()

        # wait for this thread to acquire the lock
        with self.condition:
            if not self.active_thread:
                self.condition.wait(5)
                eq_(self.active_thread, "one")

        client2 = self._get_client()
        client2.start()
        event2 = threading.Event()
        lock2 = client2.Lock(self.lockpath, "two")
        thread2 = threading.Thread(target=self._thread_lock_acquire_til_event,
            args=("two", lock2, event2))
        thread2.start()

        # this one should block in acquire. check that it is a contender
        wait(lambda: len(lock2.contenders()) > 1)
        eq_(lock2.contenders(), ["one", "two"])

        lock2.cancel()
        with self.condition:
            if not "two" in self.cancelled_threads:
                self.condition.wait()
                assert "two" in self.cancelled_threads

        eq_(lock2.contenders(), ["one"])

        thread2.join()
        event1.set()
        thread1.join()
        client2.stop()

    def test_lock_double_calls(self):
        lock1 = self.client.Lock(self.lockpath, "one")
        lock1.acquire()
        lock1.acquire()
        lock1.release()
        lock1.release()
