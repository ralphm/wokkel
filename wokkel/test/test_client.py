# Copyright (c) 2003-2007 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.client}.
"""

from twisted.trial import unittest
from twisted.words.protocols.jabber import xmlstream
from twisted.words.protocols.jabber.client import XMPPAuthenticator
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import STREAM_AUTHD_EVENT
from twisted.words.protocols.jabber.xmlstream import INIT_FAILED_EVENT

from wokkel.client import DeferredClientFactory
from wokkel.test.test_compat import BootstrapMixinTest

class DeferredClientFactoryTest(BootstrapMixinTest):


    def setUp(self):
        self.factory = DeferredClientFactory(JID('user@example.org'), 'secret')


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
