# Copyright (c) Ralph Meijer.
# See LICENSE for details

"""
Tests for L{wokkel.xmppim}.
"""

from twisted.internet import defer
from twisted.trial import unittest
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import toResponse
from twisted.words.xish import domish, utility

from wokkel import xmppim
from wokkel.generic import ErrorStanza, parseXml
from wokkel.test.helpers import XmlStreamStub

NS_XML = 'http://www.w3.org/XML/1998/namespace'
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



class AvailabilityPresenceTest(unittest.TestCase):

    def test_fromElement(self):
        xml = """<presence from='user@example.org' to='user@example.com'>
                   <show>chat</show>
                   <status>Let's chat!</status>
                   <priority>50</priority>
                 </presence>
              """

        presence = xmppim.AvailabilityPresence.fromElement(parseXml(xml))
        self.assertEquals(JID('user@example.org'), presence.sender)
        self.assertEquals(JID('user@example.com'), presence.recipient)
        self.assertTrue(presence.available)
        self.assertEquals('chat', presence.show)
        self.assertEquals({None: "Let's chat!"}, presence.statuses)
        self.assertEquals(50, presence.priority)


class PresenceProtocolTest(unittest.TestCase):
    """
    Tests for L{xmppim.PresenceProtocol}
    """

    def setUp(self):
        self.output = []
        self.protocol = xmppim.PresenceProtocol()
        self.protocol.parent = self
        self.protocol.xmlstream = utility.EventDispatcher()
        self.protocol.connectionInitialized()


    def send(self, obj):
        self.output.append(obj)


    def test_errorReceived(self):
        """
        Incoming presence stanzas are parsed and dispatched.
        """
        xml = """<presence type="error"/>"""

        def errorReceived(error):
            xmppim.PresenceProtocol.errorReceived(self.protocol, error)
            try:
                self.assertIsInstance(error, ErrorStanza)
            except:
                d.errback()
            else:
                d.callback(None)

        d = defer.Deferred()
        self.protocol.errorReceived = errorReceived
        self.protocol.xmlstream.dispatch(parseXml(xml))
        return d


    def test_availableReceived(self):
        """
        Incoming presence stanzas are parsed and dispatched.
        """
        xml = """<presence/>"""

        def availableReceived(presence):
            xmppim.PresenceProtocol.availableReceived(self.protocol, presence)
            try:
                self.assertIsInstance(presence, xmppim.AvailabilityPresence)
            except:
                d.errback()
            else:
                d.callback(None)

        d = defer.Deferred()
        self.protocol.availableReceived = availableReceived
        self.protocol.xmlstream.dispatch(parseXml(xml))
        return d


    def test_unavailableReceived(self):
        """
        Incoming presence stanzas are parsed and dispatched.
        """
        xml = """<presence type='unavailable'/>"""

        def unavailableReceived(presence):
            xmppim.PresenceProtocol.unavailableReceived(self.protocol, presence)
            try:
                self.assertIsInstance(presence, xmppim.AvailabilityPresence)
            except:
                d.errback()
            else:
                d.callback(None)

        d = defer.Deferred()
        self.protocol.unavailableReceived = unavailableReceived
        self.protocol.xmlstream.dispatch(parseXml(xml))
        return d


    def test_subscribeReceived(self):
        """
        Incoming presence stanzas are parsed and dispatched.
        """
        xml = """<presence type='subscribe'/>"""

        def subscribeReceived(presence):
            xmppim.PresenceProtocol.subscribeReceived(self.protocol, presence)
            try:
                self.assertIsInstance(presence, xmppim.SubscriptionPresence)
            except:
                d.errback()
            else:
                d.callback(None)

        d = defer.Deferred()
        self.protocol.subscribeReceived = subscribeReceived
        self.protocol.xmlstream.dispatch(parseXml(xml))
        return d


    def test_unsubscribeReceived(self):
        """
        Incoming presence stanzas are parsed and dispatched.
        """
        xml = """<presence type='unsubscribe'/>"""

        def unsubscribeReceived(presence):
            xmppim.PresenceProtocol.unsubscribeReceived(self.protocol, presence)
            try:
                self.assertIsInstance(presence, xmppim.SubscriptionPresence)
            except:
                d.errback()
            else:
                d.callback(None)

        d = defer.Deferred()
        self.protocol.unsubscribeReceived = unsubscribeReceived
        self.protocol.xmlstream.dispatch(parseXml(xml))
        return d


    def test_subscribedReceived(self):
        """
        Incoming presence stanzas are parsed and dispatched.
        """
        xml = """<presence type='subscribed'/>"""

        def subscribedReceived(presence):
            xmppim.PresenceProtocol.subscribedReceived(self.protocol, presence)
            try:
                self.assertIsInstance(presence, xmppim.SubscriptionPresence)
            except:
                d.errback()
            else:
                d.callback(None)

        d = defer.Deferred()
        self.protocol.subscribedReceived = subscribedReceived
        self.protocol.xmlstream.dispatch(parseXml(xml))
        return d


    def test_unsubscribedReceived(self):
        """
        Incoming presence stanzas are parsed and dispatched.
        """
        xml = """<presence type='unsubscribed'/>"""

        def unsubscribedReceived(presence):
            xmppim.PresenceProtocol.unsubscribedReceived(self.protocol,
                                                         presence)
            try:
                self.assertIsInstance(presence, xmppim.SubscriptionPresence)
            except:
                d.errback()
            else:
                d.callback(None)

        d = defer.Deferred()
        self.protocol.unsubscribedReceived = unsubscribedReceived
        self.protocol.xmlstream.dispatch(parseXml(xml))
        return d


    def test_probeReceived(self):
        """
        Incoming presence stanzas are parsed and dispatched.
        """
        xml = """<presence type='probe'/>"""

        def probeReceived(presence):
            xmppim.PresenceProtocol.probeReceived(self.protocol, presence)
            try:
                self.assertIsInstance(presence, xmppim.ProbePresence)
            except:
                d.errback()
            else:
                d.callback(None)

        d = defer.Deferred()
        self.protocol.probeReceived = probeReceived
        self.protocol.xmlstream.dispatch(parseXml(xml))
        return d

    def test_available(self):
        """
        It should be possible to pass a sender address.
        """
        self.protocol.available(JID('user@example.com'),
                                show=u'chat',
                                status=u'Talk to me!',
                                priority=50)
        element = self.output[-1]
        self.assertEquals("user@example.com", element.getAttribute('to'))
        self.assertIdentical(None, element.getAttribute('type'))
        self.assertEquals(u'chat', unicode(element.show))
        self.assertEquals(u'Talk to me!', unicode(element.status))
        self.assertEquals(u'50', unicode(element.priority))

    def test_availableLanguages(self):
        """
        It should be possible to pass a sender address.
        """
        self.protocol.available(JID('user@example.com'),
                                show=u'chat',
                                statuses={None: u'Talk to me!',
                                          'nl': u'Praat met me!'},
                                priority=50)
        element = self.output[-1]
        self.assertEquals("user@example.com", element.getAttribute('to'))
        self.assertIdentical(None, element.getAttribute('type'))
        self.assertEquals(u'chat', unicode(element.show))

        statuses = {}
        for status in element.elements():
            if status.name == 'status':
                lang = status.getAttribute((NS_XML, 'lang'))
                statuses[lang] = unicode(status)

        self.assertIn(None, statuses)
        self.assertEquals(u'Talk to me!', statuses[None])
        self.assertIn('nl', statuses)
        self.assertEquals(u'Praat met me!', statuses['nl'])
        self.assertEquals(u'50', unicode(element.priority))


    def test_availableSender(self):
        """
        It should be possible to pass a sender address.
        """
        self.protocol.available(JID('user@example.com'),
                                sender=JID('user@example.org'))
        element = self.output[-1]
        self.assertEquals("user@example.org", element.getAttribute('from'))


    def test_unavailableDirected(self):
        """
        Test sending of directed unavailable presence broadcast.
        """

        self.protocol.unavailable(JID('user@example.com'))
        element = self.output[-1]
        self.assertEquals("presence", element.name)
        self.assertEquals(None, element.uri)
        self.assertEquals("user@example.com", element.getAttribute('to'))
        self.assertEquals("unavailable", element.getAttribute('type'))

    def test_unavailableWithStatus(self):
        """
        Test sending of directed unavailable presence broadcast with status.
        """

        self.protocol.unavailable(JID('user@example.com'),
                                  {None: 'Disconnected'})
        element = self.output[-1]
        self.assertEquals("presence", element.name)
        self.assertEquals(None, element.uri)
        self.assertEquals("user@example.com", element.getAttribute('to'))
        self.assertEquals("unavailable", element.getAttribute('type'))
        self.assertEquals("Disconnected", unicode(element.status))


    def test_unavailableBroadcast(self):
        """
        Test sending of unavailable presence broadcast.
        """

        self.protocol.unavailable(None)
        element = self.output[-1]
        self.assertEquals("presence", element.name)
        self.assertEquals(None, element.uri)
        self.assertEquals(None, element.getAttribute('to'))
        self.assertEquals("unavailable", element.getAttribute('type'))


    def test_unavailableBroadcastNoRecipientParameter(self):
        """
        Test sending of unavailable presence broadcast by not passing entity.
        """

        self.protocol.unavailable()
        element = self.output[-1]
        self.assertEquals("presence", element.name)
        self.assertEquals(None, element.uri)
        self.assertEquals(None, element.getAttribute('to'))
        self.assertEquals("unavailable", element.getAttribute('type'))


    def test_unavailableSender(self):
        """
        It should be possible to pass a sender address.
        """
        self.protocol.unavailable(JID('user@example.com'),
                                  sender=JID('user@example.org'))
        element = self.output[-1]
        self.assertEquals("user@example.org", element.getAttribute('from'))


    def test_subscribeSender(self):
        """
        It should be possible to pass a sender address.
        """
        self.protocol.subscribe(JID('user@example.com'),
                                sender=JID('user@example.org'))
        element = self.output[-1]
        self.assertEquals("user@example.org", element.getAttribute('from'))


    def test_unsubscribeSender(self):
        """
        It should be possible to pass a sender address.
        """
        self.protocol.unsubscribe(JID('user@example.com'),
                                  sender=JID('user@example.org'))
        element = self.output[-1]
        self.assertEquals("user@example.org", element.getAttribute('from'))


    def test_subscribedSender(self):
        """
        It should be possible to pass a sender address.
        """
        self.protocol.subscribed(JID('user@example.com'),
                                 sender=JID('user@example.org'))
        element = self.output[-1]
        self.assertEquals("user@example.org", element.getAttribute('from'))


    def test_unsubscribedSender(self):
        """
        It should be possible to pass a sender address.
        """
        self.protocol.unsubscribed(JID('user@example.com'),
                                   sender=JID('user@example.org'))
        element = self.output[-1]
        self.assertEquals("user@example.org", element.getAttribute('from'))


    def test_probeSender(self):
        """
        It should be possible to pass a sender address.
        """
        self.protocol.probe(JID('user@example.com'),
                            sender=JID('user@example.org'))
        element = self.output[-1]
        self.assertEquals("user@example.org", element.getAttribute('from'))



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
