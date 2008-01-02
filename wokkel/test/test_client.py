# Copyright (c) 2003-2007 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.client}.
"""

from twisted.trial import unittest
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import STREAM_AUTHD_EVENT
from twisted.words.protocols.jabber.xmlstream import INIT_FAILED_EVENT

from wokkel.client import DeferredClientFactory

class DeferredClientFactoryTest(unittest.TestCase):

    def test_deferredOnInitialized(self):
        """
        Test the factory's deferred on stream initialization.
        """

        f = DeferredClientFactory(JID('user@example.org'), 'secret')
        xmlstream = f.buildProtocol(None)
        xmlstream.dispatch(xmlstream, STREAM_AUTHD_EVENT)
        return f.deferred

    def test_deferredOnNotInitialized(self):
        """
        Test the factory's deferred on failed stream initialization.
        """

        f = DeferredClientFactory(JID('user@example.org'), 'secret')
        xmlstream = f.buildProtocol(None)

        class TestException(Exception):
            pass

        xmlstream.dispatch(TestException(), INIT_FAILED_EVENT)
        self.assertFailure(f.deferred, TestException)
        return f.deferred

    def test_deferredOnConnectionFailure(self):
        """
        Test the factory's deferred on connection faulure.
        """

        f = DeferredClientFactory(JID('user@example.org'), 'secret')
        xmlstream = f.buildProtocol(None)

        class TestException(Exception):
            pass

        f.clientConnectionFailed(self, TestException())
        self.assertFailure(f.deferred, TestException)
        return f.deferred
