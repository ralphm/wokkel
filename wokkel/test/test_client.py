# Copyright (c) 2003-2007 Ralph Meijer
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

from wokkel import client
from wokkel.test.test_compat import BootstrapMixinTest

class DeferredClientFactoryTest(BootstrapMixinTest):
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

        xs = self.factory.buildProtocol(None)
        self.factory.clientConnectionFailed(self, TestException())
        self.assertFailure(self.factory.deferred, TestException)
        return self.factory.deferred



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
            self.assertEqual('example.org', connector.domain)
            self.assertEqual(factory, connector.factory)

        def connect(connector):
            d1.callback(connector)

        d1.addCallback(cb)
        self.patch(client.SRVConnector, 'connect', connect)

        d2 = client.clientCreator(factory)
        self.assertEqual(factory.deferred, d2)

        return d1
