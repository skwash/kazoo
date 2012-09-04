=====
kazoo
=====

Kazoo is a Python library designed to make working with :term:`Zookeeper` a
more hassle-free experience that is less prone to errors.

Kazoo features:

* Support for gevent 0.13 and gevent 1.0b
* Unified asynchronous API for use with greenlets or threads
* Lock, Party, Election, and Partitioner recipe implementations (more
  implementations are in development)
* Data and Children Watchers
* Integrated testing helpers for Zookeeper clusters
* Simplified Zookeeper connection state tracking
* Pure-Python based implementation of the wire protocol, avoiding all the
  memory leaks, lacking features and debugging madness of the C library

Kazoo is heavily inspired by `Netflix Curator`_ simplifications and helpers.

.. note::

    You should be familiar with Zookeeper and have read the `Zookeeper
    Programmers Guide`_ before using `kazoo`.

Reference Docs
==============

.. toctree::
   :maxdepth: 1

   install
   basic_usage
   async_usage
   implementation
   testing
   api
   Changelog <changelog>

Why
===

Using :term:`Zookeeper` in a safe manner can be difficult due to the variety of
edge-cases in :term:`Zookeeper` and other bugs that have been present in the
Python C binding. Due to how the C library utilizes a separate C thread for
:term:`Zookeeper` communication some libraries like `gevent`_ also don't work
properly by default. Kazoo handles all of these cases and provides a new
asynchronous API which is consistent when using threads or `gevent`_ greenlets.

Source Code
===========

All source code is available on `github under kazoo <https://github.com/python-
zk/kazoo>`_.

Bugs/Support
============

Bugs and support issues should be reported on the `kazoo github issue tracker
<https://github.com/python-zk/kazoo/issues>`_.

The developers of ``kazoo`` can frequently be found on the Freenode IRC
network in the #zookeeper channel.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`glossary`

.. toctree::
   :hidden:

   glossary

License
=======

``kazoo`` is offered under the Apache License 2.0.

Authors
=======

``kazoo`` started under the `Nimbus Project`_ and through collaboration with
the open-source community has been merged with code from `Mozilla`_ and the
`Zope Corporation`_.

.. _Apache Zookeeper: http://zookeeper.apache.org/
.. _Zookeeper Programmers Guide: http://zookeeper.apache.org/doc/trunk/zookeeperProgrammers.html
.. _Zookeeper Recipes: http://zookeeper.apache.org/doc/current/recipes.html#sc_recoverableSharedLocks
.. _Nimbus Project: http://www.nimbusproject.org/
.. _Zope Corporation: http://zope.com/
.. _Mozilla: http://www.mozilla.org/
.. _Netflix Curator: https://github.com/Netflix/curator
.. _gevent: http://gevent.org/
