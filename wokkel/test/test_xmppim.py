# Copyright (c) Ralph Meijer.
# See LICENSE for details

"""
Tests for L{wokkel.xmppim}.
"""

from __future__ import division, absolute_import

from twisted.internet import defer
from twisted.trial import unittest
from twisted.python.compat import unicode
from twisted.words.protocols.jabber import error
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import toResponse
from twisted.words.xish import domish, utility

from wokkel import xmppim
from wokkel.generic import ErrorStanza, parseXml
from wokkel.test.helpers import TestableRequestHandlerMixin, XmlStreamStub

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



class RosterItemTest(unittest.TestCase):
    """
    Tests for L{xmppim.RosterItem}.
    """

    def test_toElement(self):
        """
        A roster item has the correct namespace/name, lacks unset attributes.
        """
        item = xmppim.RosterItem(JID('user@example.org'))
        element = item.toElement()
        self.assertEqual('item', element.name)
        self.assertEqual(NS_ROSTER, element.uri)
        self.assertFalse(element.hasAttribute('subscription'))
        self.assertFalse(element.hasAttribute('ask'))
        self.assertEqual(u"", element.getAttribute('name', u""))
        self.assertFalse(element.hasAttribute('approved'))
        self.assertEquals(0, len(list(element.elements())))


    def test_toElementMinimal(self):
        """
        A bare roster item only has a jid attribute.
        """
        item = xmppim.RosterItem(JID('user@example.org'))
        element = item.toElement()
        self.assertEqual(u'user@example.org', element.getAttribute('jid'))


    def test_toElementSubscriptionNone(self):
        """
        A roster item with no subscription has no subscription attribute.
        """
        item = xmppim.RosterItem(JID('user@example.org'),
                                 subscriptionTo=False,
                                 subscriptionFrom=False)
        element = item.toElement()
        self.assertIdentical(None, element.getAttribute('subscription'))


    def test_toElementSubscriptionTo(self):
        """
        A roster item with subscriptionTo set has subscription 'to'.
        """
        item = xmppim.RosterItem(JID('user@example.org'),
                                 subscriptionTo=True,
                                 subscriptionFrom=False)
        element = item.toElement()
        self.assertEqual('to', element.getAttribute('subscription'))


    def test_toElementSubscriptionFrom(self):
        """
        A roster item with subscriptionFrom set has subscription 'to'.
        """
        item = xmppim.RosterItem(JID('user@example.org'),
                                 subscriptionTo=False,
                                 subscriptionFrom=True)
        element = item.toElement()
        self.assertEqual('from', element.getAttribute('subscription'))


    def test_toElementSubscriptionBoth(self):
        """
        A roster item with mutual subscription has subscription 'both'.
        """
        item = xmppim.RosterItem(JID('user@example.org'),
                                 subscriptionTo=True,
                                 subscriptionFrom=True)
        element = item.toElement()
        self.assertEqual('both', element.getAttribute('subscription'))


    def test_toElementSubscriptionRemove(self):
        """
        A roster item with remove set has subscription 'remove'.
        """
        item = xmppim.RosterItem(JID('user@example.org'))
        item.remove = True
        element = item.toElement()
        self.assertEqual('remove', element.getAttribute('subscription'))


    def test_toElementAsk(self):
        """
        A roster item with pendingOut set has subscription 'ask'.
        """
        item = xmppim.RosterItem(JID('user@example.org'))
        item.pendingOut = True
        element = item.toElement()
        self.assertEqual('subscribe', element.getAttribute('ask'))


    def test_toElementName(self):
        """
        A roster item's name is rendered to the 'name' attribute.
        """
        item = xmppim.RosterItem(JID('user@example.org'),
                                 name='Joe User')
        element = item.toElement()
        self.assertEqual(u'Joe User', element.getAttribute('name'))


    def test_toElementGroups(self):
        """
        A roster item's groups are rendered as 'group' child elements.
        """
        groups = set(['Friends', 'Jabber'])
        item = xmppim.RosterItem(JID('user@example.org'),
                                 groups=groups)

        element = item.toElement()
        foundGroups = set()
        for child in element.elements():
            if child.uri == NS_ROSTER and child.name == 'group':
                foundGroups.add(unicode(child))

        self.assertEqual(groups, foundGroups)


    def test_toElementApproved(self):
        """
        A pre-approved subscription for a roster item has an 'approved' flag.
        """
        item = xmppim.RosterItem(JID('user@example.org'))
        item.approved = True
        element = item.toElement()
        self.assertEqual(u'true', element.getAttribute('approved'))


    def test_fromElementMinimal(self):
        """
        A minimal roster item has a reference to the JID of the contact.
        """

        xml = """
            <item xmlns="jabber:iq:roster"
                  jid="test@example.org"/>
        """

        item = xmppim.RosterItem.fromElement(parseXml(xml))
        self.assertEqual(JID(u"test@example.org"), item.entity)
        self.assertEqual(u"", item.name)
        self.assertFalse(item.subscriptionTo)
        self.assertFalse(item.subscriptionFrom)
        self.assertFalse(item.pendingOut)
        self.assertFalse(item.approved)
        self.assertEqual(set(), item.groups)


    def test_fromElementName(self):
        """
        A roster item may have an optional name.
        """

        xml = """
            <item xmlns="jabber:iq:roster"
                  jid="test@example.org"
                  name="Test User"/>
        """

        item = xmppim.RosterItem.fromElement(parseXml(xml))
        self.assertEqual(u"Test User", item.name)


    def test_fromElementGroups(self):
        """
        A roster item may have one or more groups.
        """

        xml = """
            <item xmlns="jabber:iq:roster"
                  jid="test@example.org">
              <group>Friends</group>
              <group>Twisted</group>
            </item>
        """

        item = xmppim.RosterItem.fromElement(parseXml(xml))
        self.assertIn(u"Twisted", item.groups)
        self.assertIn(u"Friends", item.groups)


    def test_fromElementSubscriptionNone(self):
        """
        Subscription 'none' sets both attributes to False.
        """

        xml = """
            <item xmlns="jabber:iq:roster"
                  jid="test@example.org"
                  subscription="none"/>
        """

        item = xmppim.RosterItem.fromElement(parseXml(xml))
        self.assertFalse(item.remove)
        self.assertFalse(item.subscriptionTo)
        self.assertFalse(item.subscriptionFrom)


    def test_fromElementSubscriptionTo(self):
        """
        Subscription 'to' sets the corresponding attribute to True.
        """

        xml = """
            <item xmlns="jabber:iq:roster"
                  jid="test@example.org"
                  subscription="to"/>
        """

        item = xmppim.RosterItem.fromElement(parseXml(xml))
        self.assertFalse(item.remove)
        self.assertTrue(item.subscriptionTo)
        self.assertFalse(item.subscriptionFrom)


    def test_fromElementSubscriptionFrom(self):
        """
        Subscription 'from' sets the corresponding attribute to True.
        """

        xml = """
            <item xmlns="jabber:iq:roster"
                  jid="test@example.org"
                  subscription="from"/>
        """

        item = xmppim.RosterItem.fromElement(parseXml(xml))
        self.assertFalse(item.remove)
        self.assertFalse(item.subscriptionTo)
        self.assertTrue(item.subscriptionFrom)


    def test_fromElementSubscriptionBoth(self):
        """
        Subscription 'both' sets both attributes to True.
        """

        xml = """
            <item xmlns="jabber:iq:roster"
                  jid="test@example.org"
                  subscription="both"/>
        """

        item = xmppim.RosterItem.fromElement(parseXml(xml))
        self.assertFalse(item.remove)
        self.assertTrue(item.subscriptionTo)
        self.assertTrue(item.subscriptionFrom)


    def test_fromElementSubscriptionRemove(self):
        """
        Subscription 'remove' sets the remove attribute.
        """

        xml = """
            <item xmlns="jabber:iq:roster"
                  jid="test@example.org"
                  subscription="remove"/>
        """

        item = xmppim.RosterItem.fromElement(parseXml(xml))
        self.assertTrue(item.remove)


    def test_fromElementPendingOut(self):
        """
        The ask attribute, if set to 'subscription', means pending out.
        """

        xml = """
            <item xmlns="jabber:iq:roster"
                  jid="test@example.org"
                  ask="subscribe"/>
        """

        item = xmppim.RosterItem.fromElement(parseXml(xml))
        self.assertTrue(item.pendingOut)


    def test_fromElementApprovedTrue(self):
        """
        The approved attribute (true) signals a pre-approved subscription.
        """

        xml = """
            <item xmlns="jabber:iq:roster"
                  jid="test@example.org"
                  approved="true"/>
        """

        item = xmppim.RosterItem.fromElement(parseXml(xml))
        self.assertTrue(item.approved)


    def test_fromElementApproved1(self):
        """
        The approved attribute (1) signals a pre-approved subscription.
        """

        xml = """
            <item xmlns="jabber:iq:roster"
                  jid="test@example.org"
                  approved="1"/>
        """

        item = xmppim.RosterItem.fromElement(parseXml(xml))
        self.assertTrue(item.approved)


    def test_jidDeprecationGet(self):
        """
        Getting the jid attribute works as entity and warns deprecation.
        """
        item = xmppim.RosterItem(JID('user@example.org'))
        entity = self.assertWarns(DeprecationWarning,
                                  "wokkel.xmppim.RosterItem.jid was "
                                  "deprecated in Wokkel 0.7.1; "
                                  "please use RosterItem.entity instead.",
                                  xmppim.__file__,
                                  getattr, item, 'jid')
        self.assertIdentical(entity, item.entity)


    def test_jidDeprecationSet(self):
        """
        Setting the jid attribute works as entity and warns deprecation.
        """
        item = xmppim.RosterItem(JID('user@example.org'))
        self.assertWarns(DeprecationWarning,
                         "wokkel.xmppim.RosterItem.jid was deprecated "
                         "in Wokkel 0.7.1; "
                         "please use RosterItem.entity instead.",
                         xmppim.__file__,
                         setattr, item, 'jid',
                         JID('other@example.org'))
        self.assertEqual(JID('other@example.org'), item.entity)


    def test_askDeprecationGet(self):
        """
        Getting the ask attribute works as entity and warns deprecation.
        """
        item = xmppim.RosterItem(JID('user@example.org'))
        item.pendingOut = True
        ask = self.assertWarns(DeprecationWarning,
                               "wokkel.xmppim.RosterItem.ask was "
                               "deprecated in Wokkel 0.7.1; "
                               "please use RosterItem.pendingOut instead.",
                               xmppim.__file__,
                               getattr, item, 'ask')
        self.assertTrue(ask)


    def test_askDeprecationSet(self):
        """
        Setting the ask attribute works as entity and warns deprecation.
        """
        item = xmppim.RosterItem(JID('user@example.org'))
        self.assertWarns(DeprecationWarning,
                         "wokkel.xmppim.RosterItem.ask was "
                         "deprecated in Wokkel 0.7.1; "
                         "please use RosterItem.pendingOut instead.",
                         xmppim.__file__,
                         setattr, item, 'ask',
                         True)
        self.assertTrue(item.pendingOut)



class RosterRequestTest(unittest.TestCase):
    """
    Tests for L{xmppim.RosterRequest}.
    """

    def test_fromElement(self):
        """
        A bare roster request is parsed and missing information is None.
        """
        xml = """
            <iq type='get' to='this@example.org/Home' from='this@example.org'>
              <query xmlns='jabber:iq:roster'/>
            </iq>
        """

        request = xmppim.RosterRequest.fromElement(parseXml(xml))
        self.assertEqual('get', request.stanzaType)
        self.assertEqual(JID('this@example.org/Home'), request.recipient)
        self.assertEqual(JID('this@example.org'), request.sender)
        self.assertEqual(None, request.item)
        self.assertEqual(None, request.version)


    def test_fromElementItem(self):
        """
        If an item is present, parse it and put it in the request item.
        """
        xml = """
            <iq type='set' to='this@example.org/Home' from='this@example.org'>
              <query xmlns='jabber:iq:roster'>
                <item jid='user@example.org'/>
              </query>
            </iq>
        """

        request = xmppim.RosterRequest.fromElement(parseXml(xml))
        self.assertNotIdentical(None, request.item)
        self.assertEqual(JID('user@example.org'), request.item.entity)


    def test_fromElementVersion(self):
        """
        If a ver attribute is present, put it in the request version.
        """
        xml = """
            <iq type='set' to='this@example.org/Home' from='this@example.org'>
              <query xmlns='jabber:iq:roster' ver='ver72'>
                <item jid='user@example.org'/>
              </query>
            </iq>
        """
        request = xmppim.RosterRequest.fromElement(parseXml(xml))
        self.assertEqual('ver72', request.version)


    def test_fromElementVersionEmpty(self):
        """
        The ver attribute may be empty.
        """
        xml = """
            <iq type='get' to='this@example.org/Home' from='this@example.org'>
              <query xmlns='jabber:iq:roster' ver=''/>
            </iq>
        """
        request = xmppim.RosterRequest.fromElement(parseXml(xml))
        self.assertEqual('', request.version)


    def test_toElement(self):
        """
        A roster request has a query element in the roster namespace.
        """
        request = xmppim.RosterRequest()
        element = request.toElement()
        children = element.elements()
        child = next(children)
        self.assertEqual(NS_ROSTER, child.uri)
        self.assertEqual('query', child.name)


    def test_toElementItem(self):
        """
        If an item is set, it is rendered as a child of the query.
        """
        request = xmppim.RosterRequest()
        request.item = xmppim.RosterItem(JID('user@example.org'))
        element = request.toElement()
        children = element.query.elements()
        child = next(children)
        self.assertEqual(NS_ROSTER, child.uri)
        self.assertEqual('item', child.name)



class FakeClient(object):
    """
    Fake client stream manager for roster tests.
    """

    def __init__(self, xmlstream, jid):
        self.xmlstream = xmlstream
        self.jid = jid


    def request(self, request):
        element = request.toElement()
        self.xmlstream.send(element)
        return defer.Deferred()


    def addHandler(self, handler):
        handler.makeConnection(self.xmlstream)
        handler.connectionInitialized()


    def test_toElementVersion(self):
        """
        If the roster version is set, a 'ver' attribute is added.
        """
        request = xmppim.RosterRequest()
        request.version = 'ver72'
        element = request.toElement()
        self.assertEqual('ver72', element.query.getAttribute('ver'))


    def test_toElementVersionEmpty(self):
        """
        If the roster version is the empty string, it should add 'ver', too.
        """
        request = xmppim.RosterRequest()
        request.version = ''
        element = request.toElement()
        self.assertEqual('', element.query.getAttribute('ver'))



class RosterClientProtocolTest(unittest.TestCase, TestableRequestHandlerMixin):
    """
    Tests for L{xmppim.RosterClientProtocol}.
    """

    def setUp(self):
        self.stub = XmlStreamStub()
        self.client = FakeClient(self.stub.xmlstream, JID('this@example.org'))
        self.service = xmppim.RosterClientProtocol()
        self.service.setHandlerParent(self.client)


    def test_setItem(self):
        """
        Setting a roster item renders the item and sends it out.
        """
        item = xmppim.RosterItem(JID('test@example.org'),
                                 name='Joe User',
                                 groups=set(['Friends', 'Jabber']))
        d = self.service.setItem(item)

        # Inspect outgoing iq request

        iq = self.stub.output[-1]
        self.assertEqual('set', iq.getAttribute('type'))
        self.assertNotIdentical(None, iq.query)
        self.assertEqual(NS_ROSTER, iq.query.uri)

        children = list(domish.generateElementsQNamed(iq.query.children,
                                                      'item', NS_ROSTER))
        self.assertEqual(1, len(children))
        child = children[0]
        self.assertEqual('test@example.org', child['jid'])
        self.assertIdentical(None, child.getAttribute('subscription'))

        # Fake successful response

        response = toResponse(iq, 'result')
        d.callback(response)
        return d


    def test_setItemIgnoreAttributes(self):
        """
        Certain attributes should be rendered for roster set.
        """
        item = xmppim.RosterItem(JID('test@example.org'),
                                 subscriptionTo=True,
                                 subscriptionFrom=False,
                                 name='Joe User',
                                 groups=set(['Friends', 'Jabber']))
        item.pendingOut = True
        item.approved = True
        d = self.service.setItem(item)

        # Inspect outgoing iq request

        iq = self.stub.output[-1]
        self.assertEqual('set', iq.getAttribute('type'))
        self.assertNotIdentical(None, iq.query)
        self.assertEqual(NS_ROSTER, iq.query.uri)

        children = list(domish.generateElementsQNamed(iq.query.children,
                                                      'item', NS_ROSTER))
        self.assertEqual(1, len(children))
        child = children[0]
        self.assertIdentical(None, child.getAttribute('ask'))
        self.assertIdentical(None, child.getAttribute('approved'))
        self.assertIdentical(None, child.getAttribute('subscription'))

        # Fake successful response

        response = toResponse(iq, 'result')
        d.callback(response)
        return d


    def test_removeItem(self):
        """
        Removing a roster item is setting an item with subscription C{remove}.
        """
        d = self.service.removeItem(JID('test@example.org'))

        # Inspect outgoing iq request

        iq = self.stub.output[-1]
        self.assertEqual('set', iq.getAttribute('type'))
        self.assertNotIdentical(None, iq.query)
        self.assertEqual(NS_ROSTER, iq.query.uri)

        children = list(domish.generateElementsQNamed(iq.query.children,
                                                      'item', NS_ROSTER))
        self.assertEqual(1, len(children))
        child = children[0]
        self.assertEqual('test@example.org', child['jid'])
        self.assertEqual('remove', child.getAttribute('subscription'))

        # Fake successful response

        response = toResponse(iq, 'result')
        d.callback(response)
        return d


    def test_getRoster(self):
        """
        A request for the roster is sent out and the response is parsed.
        """
        def cb(roster):
            self.assertIn(JID('user@example.org'), roster)
            self.assertIdentical(None, getattr(roster, 'version'))

        d = self.service.getRoster()
        d.addCallback(cb)

        # Inspect outgoing iq request

        iq = self.stub.output[-1]
        self.assertEqual('get', iq.getAttribute('type'))
        self.assertNotIdentical(None, iq.query)
        self.assertEqual(NS_ROSTER, iq.query.uri)
        self.assertFalse(iq.query.hasAttribute('ver'))

        # Fake successful response
        response = toResponse(iq, 'result')
        query = response.addElement((NS_ROSTER, 'query'))
        item = query.addElement('item')
        item['jid'] = 'user@example.org'

        d.callback(response)
        return d


    def test_getRosterVer(self):
        """
        A request for the roster with version passes the version on.
        """
        def cb(roster):
            self.assertEqual('ver96', getattr(roster, 'version'))

        d = self.service.getRoster(version='ver72')
        d.addCallback(cb)

        # Inspect outgoing iq request

        iq = self.stub.output[-1]
        self.assertEqual('ver72', iq.query.getAttribute('ver'))

        # Fake successful response
        response = toResponse(iq, 'result')
        query = response.addElement((NS_ROSTER, 'query'))
        query['ver'] = 'ver96'
        item = query.addElement('item')
        item['jid'] = 'user@example.org'

        d.callback(response)
        return d


    def test_getRosterVerEmptyResult(self):
        """
        An empty response is returned as None.
        """
        def cb(response):
            self.assertIdentical(None, response)

        d = self.service.getRoster(version='ver72')
        d.addCallback(cb)

        # Inspect outgoing iq request

        iq = self.stub.output[-1]

        # Fake successful response
        response = toResponse(iq, 'result')
        d.callback(response)
        return d


    def test_onRosterSet(self):
        """
        A roster push causes onRosterSet to be called with the parsed item.
        """
        xml = """
          <iq type='set'>
            <query xmlns='jabber:iq:roster'>
              <item jid='user@example.org'/>
            </query>
          </iq>
        """

        items = []

        def onRosterSet(item):
            items.append(item)

        def cb(result):
            self.assertEqual(1, len(items))
            self.assertEqual(JID('user@example.org'), items[0].entity)

        self.service.onRosterSet = onRosterSet

        d = self.assertWarns(DeprecationWarning,
                             "wokkel.xmppim.RosterClientProtocol.onRosterSet "
                             "was deprecated in Wokkel 0.7.1; "
                             "please use RosterClientProtocol.setReceived "
                             "instead.",
                             xmppim.__file__,
                             self.handleRequest, xml)
        d.addCallback(cb)
        return d


    def test_onRosterRemove(self):
        """
        A roster push causes onRosterSet to be called with the parsed item.
        """
        xml = """
          <iq type='set'>
            <query xmlns='jabber:iq:roster'>
              <item jid='user@example.org' subscription='remove'/>
            </query>
          </iq>
        """

        entities = []

        def onRosterRemove(entity):
            entities.append(entity)

        def cb(result):
            self.assertEqual([JID('user@example.org')], entities)

        self.service.onRosterRemove = onRosterRemove

        d = self.assertWarns(DeprecationWarning,
                             "wokkel.xmppim.RosterClientProtocol.onRosterRemove "
                             "was deprecated in Wokkel 0.7.1; "
                             "please use RosterClientProtocol.removeReceived "
                             "instead.",
                             xmppim.__file__,
                             self.handleRequest, xml)
        d.addCallback(cb)
        return d


    def test_setReceived(self):
        """
        A roster set push causes setReceived.
        """
        xml = """
          <iq type='set'>
            <query xmlns='jabber:iq:roster'>
              <item jid='user@example.org'/>
            </query>
          </iq>
        """

        requests = []

        def setReceived(request):
            requests.append(request)

        def cb(result):
            self.assertEqual(1, len(requests), "setReceived was not called")
            self.assertEqual(JID('user@example.org'), requests[0].item.entity)

        self.service.setReceived = setReceived

        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_setReceivedOtherSource(self):
        """
        Roster pushes can be sent from other entities, too, ignore them.
        """
        xml = """
          <iq type='set' to='this@example.org/Home' from='other@example.org'>
            <query xmlns='jabber:iq:roster'>
              <item jid='user@example.org'/>
            </query>
          </iq>
        """

        def cb(result):
            self.assertEquals('service-unavailable', result.condition)

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_setReceivedOtherSourceAllowed(self):
        """
        Roster pushes can be sent from other entities, allow them.
        """
        xml = """
          <iq type='set' to='this@example.org/Home' from='other@example.org'>
            <query xmlns='jabber:iq:roster'>
              <item jid='user@example.org'/>
            </query>
          </iq>
        """

        self.service.allowAnySender = True
        requests = []

        def setReceived(request):
            requests.append(request)

        def cb(result):
            self.assertEqual(1, len(requests), "setReceived was not called")

        self.service.setReceived = setReceived

        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_setReceivedOtherSourceIgnored(self):
        """
        Roster pushes can be sent from other entities, allow them.
        """
        xml = """
          <iq type='set' to='this@example.org/Home' from='bad@example.org'>
            <query xmlns='jabber:iq:roster'>
              <item jid='user@example.org'/>
            </query>
          </iq>
        """

        self.service.allowAnySender = True

        def setReceived(request):
            if request.sender == JID('bad@example.org'):
                raise xmppim.RosterPushIgnored()

        def cb(result):
            self.assertEquals('service-unavailable', result.condition)

        self.service.setReceived = setReceived


        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_removeReceived(self):
        """
        A roster remove push causes removeReceived.
        """
        xml = """
          <iq type='set'>
            <query xmlns='jabber:iq:roster'>
              <item jid='user@example.org' subscription='remove'/>
            </query>
          </iq>
        """

        requests = []

        def removeReceived(request):
            requests.append(request)

        def cb(result):
            self.assertEqual(1, len(requests), "removeReceived was not called")
            self.assertEqual(JID('user@example.org'), requests[0].item.entity)

        self.service.removeReceived = removeReceived

        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d
