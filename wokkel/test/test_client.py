# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.client}.
"""

from twisted.internet import defer
from twisted.trial import unittest
from twisted.words.protocols.jabber import xmlstream
from twisted.words.protocols.jabber.client import XMPPAuthenticator
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import STREAM_AUTHD_EVENT
from twisted.words.protocols.jabber.xmlstream import INIT_FAILED_EVENT
from twisted.words.protocols.jabber.xmlstream import XMPPHandler

from wokkel import client

class XMPPClientTest(unittest.TestCase):
    """
    Tests for L{client.XMPPClient}.
    """

    def setUp(self):
        self.client = client.XMPPClient(JID('user@example.org'), 'secret')


    def test_jid(self):
        """
        Make sure the JID we pass is stored on the client.
        """
        self.assertEquals(JID('user@example.org'), self.client.jid)


    def test_jidWhenInitialized(self):
        """
        Make sure that upon login, the JID is updated from the authenticator.
        """
        xs = self.client.factory.buildProtocol(None)
        self.client.factory.authenticator.jid = JID('user@example.org/test')
        xs.dispatch(xs, xmlstream.STREAM_AUTHD_EVENT)
        self.assertEquals(JID('user@example.org/test'), self.client.jid)


    def test_domain(self):
        """
        The domain to connect to is a byte string derived from the JID host.
        """
        self.assertIsInstance(self.client.domain, bytes)
        self.assertEqual(b'example.org', self.client.domain)


    def test_bindAddress(self):
        """
        Make sure we can specify a different bindAddress when connecting client
        """
        from twisted.internet import reactor

        bind_client = client.XMPPClient(JID('user@example.org'), 'secret',
                                        host='localhost',
                                        bindAddress=('127.0.0.1', 5000))

        d = defer.Deferred()
        bind_client.startService()
        bind_client.stopService()

        # start and stop service don't fire any callbacks
        # wait 100ms to properly open connection during test
        # we need to keep reactor clean for tests
        reactor.callLater(0.1, lambda: d.callback(None))
        return d


class DeferredClientFactoryTest(unittest.TestCase):
    """
    Tests for L{client.DeferredClientFactory}.
    """

    def setUp(self):
        self.factory = client.DeferredClientFactory(JID('user@example.org'),
                                                    'secret')


    def test_buildProtocol(self):
        """
        The authenticator factory should be passed to its protocol and it
        should instantiate the authenticator and save it.
        L{xmlstream.XmlStream}s do that, but we also want to ensure it really
        is one.
        """
        xs = self.factory.buildProtocol(None)
        self.assertIdentical(self.factory, xs.factory)
        self.assertIsInstance(xs, xmlstream.XmlStream)
        self.assertIsInstance(xs.authenticator, XMPPAuthenticator)


    def test_deferredOnInitialized(self):
        """
        Test the factory's deferred on stream initialization.
        """

        xs = self.factory.buildProtocol(None)
        xs.dispatch(xs, STREAM_AUTHD_EVENT)
        return self.factory.deferred


    def test_deferredOnNotInitialized(self):
        """
        Test the factory's deferred on failed stream initialization.
        """

        class TestException(Exception):
            pass

        xs = self.factory.buildProtocol(None)
        xs.dispatch(TestException(), INIT_FAILED_EVENT)
        self.assertFailure(self.factory.deferred, TestException)
        return self.factory.deferred


    def test_deferredOnConnectionFailure(self):
        """
        Test the factory's deferred on connection faulure.
        """

        class TestException(Exception):
            pass

        self.factory.buildProtocol(None)
        self.factory.clientConnectionFailed(self, TestException())
        self.assertFailure(self.factory.deferred, TestException)
        return self.factory.deferred


    def test_addHandler(self):
        """
        Test the addition of a protocol handler.
        """
        handler = XMPPHandler()
        handler.setHandlerParent(self.factory.streamManager)
        self.assertIn(handler, self.factory.streamManager)
        self.assertIdentical(self.factory.streamManager, handler.parent)


    def test_removeHandler(self):
        """
        Test removal of a protocol handler.
        """
        handler = XMPPHandler()
        handler.setHandlerParent(self.factory.streamManager)
        handler.disownHandlerParent(self.factory.streamManager)
        self.assertNotIn(handler, self.factory.streamManager)
        self.assertIdentical(None, handler.parent)



class ClientCreatorTest(unittest.TestCase):
    """
    Tests for L{client.clientCreator}.
    """

    def test_call(self):
        """
        The factory is passed to an SRVConnector and a connection initiated.
        """

        d1 = defer.Deferred()
        factory = client.DeferredClientFactory(JID('user@example.org'),
                                               'secret')

        def cb(connector):
            self.assertEqual('xmpp-client', connector.service)
            self.assertIsInstance(connector.domain, bytes)
            self.assertEqual(b'example.org', connector.domain)
            self.assertEqual(factory, connector.factory)

        def connect(connector):
            d1.callback(connector)

        d1.addCallback(cb)
        self.patch(client.SRVConnector, 'connect', connect)

        d2 = client.clientCreator(factory)
        self.assertEqual(factory.deferred, d2)

        return d1
