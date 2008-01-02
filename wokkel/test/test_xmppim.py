# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details

"""
Tests for L{wokkel.xmppim}.
"""

from twisted.trial import unittest
from twisted.words.protocols.jabber.jid import JID
from wokkel import xmppim

class PresenceClientProtocolTest(unittest.TestCase):
    def setUp(self):
        self.output = []
        self.protocol = xmppim.PresenceClientProtocol()
        self.protocol.parent = self

    def send(self, obj):
        self.output.append(obj)

    def test_unavailableDirected(self):
        """
        Test sending of directed unavailable presence broadcast.
        """

        self.protocol.unavailable(JID('user@example.com'))
        presence = self.output[-1]
        self.assertEquals("presence", presence.name)
        self.assertEquals(None, presence.uri)
        self.assertEquals("user@example.com", presence.getAttribute('to'))
        self.assertEquals("unavailable", presence.getAttribute('type'))

    def test_unavailableWithStatus(self):
        """
        Test sending of directed unavailable presence broadcast with status.
        """

        self.protocol.unavailable(JID('user@example.com'),
                                  {None: 'Disconnected'})
        presence = self.output[-1]
        self.assertEquals("presence", presence.name)
        self.assertEquals(None, presence.uri)
        self.assertEquals("user@example.com", presence.getAttribute('to'))
        self.assertEquals("unavailable", presence.getAttribute('type'))
        self.assertEquals("Disconnected", unicode(presence.status))

    def test_unavailableBroadcast(self):
        """
        Test sending of unavailable presence broadcast.
        """

        self.protocol.unavailable(None)
        presence = self.output[-1]
        self.assertEquals("presence", presence.name)
        self.assertEquals(None, presence.uri)
        self.assertEquals(None, presence.getAttribute('to'))
        self.assertEquals("unavailable", presence.getAttribute('type'))

    def test_unavailableBroadcastNoEntityParameter(self):
        """
        Test sending of unavailable presence broadcast by not passing entity.
        """

        self.protocol.unavailable()
        presence = self.output[-1]
        self.assertEquals("presence", presence.name)
        self.assertEquals(None, presence.uri)
        self.assertEquals(None, presence.getAttribute('to'))
        self.assertEquals("unavailable", presence.getAttribute('type'))
