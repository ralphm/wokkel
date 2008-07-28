# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details

"""
Tests for L{wokkel.xmppim}.
"""

from twisted.trial import unittest
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import toResponse
from twisted.words.xish import domish

from wokkel import xmppim
from wokkel.test.helpers import XmlStreamStub

NS_ROSTER = 'jabber:iq:roster'

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


class RosterClientProtocolTest(unittest.TestCase):
    """
    Tests for L{xmppim.RosterClientProtocol}.
    """

    def setUp(self):
        self.stub = XmlStreamStub()
        self.protocol = xmppim.RosterClientProtocol()
        self.protocol.xmlstream = self.stub.xmlstream
        self.protocol.connectionInitialized()


    def test_removeItem(self):
        """
        Removing a roster item is setting an item with subscription C{remove}.
        """
        d = self.protocol.removeItem(JID('test@example.org'))

        # Inspect outgoing iq request

        iq = self.stub.output[-1]
        self.assertEquals('set', iq.getAttribute('type'))
        self.assertNotIdentical(None, iq.query)
        self.assertEquals(NS_ROSTER, iq.query.uri)

        children = list(domish.generateElementsQNamed(iq.query.children,
                                                      'item', NS_ROSTER))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test@example.org', child['jid'])
        self.assertEquals('remove', child['subscription'])

        # Fake successful response

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d
