# -*- test-case-name: wokkel.test.test_xmppim -*-
#
# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
XMPP IM protocol support.

This module provides generic implementations for the protocols defined in
U{RFC 3921<http://www.xmpp.org/rfcs/rfc3921.html>} (XMPP IM).

All of it should eventually move to Twisted.
"""

from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import IQ
from twisted.words.xish import domish

from wokkel.subprotocols import XMPPHandler

NS_XML = 'http://www.w3.org/XML/1998/namespace'
NS_ROSTER = 'jabber:iq:roster'

class Presence(domish.Element):
    def __init__(self, to=None, type=None):
        domish.Element.__init__(self, (None, "presence"))
        if type:
            self["type"] = type

        if to is not None:
            self["to"] = to.full()

class AvailablePresence(Presence):
    def __init__(self, to=None, show=None, statuses=None, priority=0):
        Presence.__init__(self, to, type=None)

        if show in ['away', 'xa', 'chat', 'dnd']:
            self.addElement('show', content=show)

        if statuses is not None:
            for lang, status in statuses.iteritems():
                s = self.addElement('status', content=status)
                if lang:
                    s[(NS_XML, "lang")] = lang

        if priority != 0:
            self.addElement('priority', content=unicode(int(priority)))

class UnavailablePresence(Presence):
    def __init__(self, to=None, statuses=None):
        Presence.__init__(self, to, type='unavailable')

        if statuses is not None:
            for lang, status in statuses.iteritems():
                s = self.addElement('status', content=status)
                if lang:
                    s[(NS_XML, "lang")] = lang

class PresenceClientProtocol(XMPPHandler):

    def connectionInitialized(self):
        self.xmlstream.addObserver('/presence', self._onPresence)

    def _getStatuses(self, presence):
        statuses = {}
        for element in presence.elements():
            if element.name == 'status':
                lang = element.getAttribute((NS_XML, 'lang'))
                text = unicode(element)
                statuses[lang] = text
        return statuses

    def _onPresence(self, presence):
        type = presence.getAttribute("type", "available")
        try:
            handler = getattr(self, '_onPresence%s' % (type.capitalize()))
        except AttributeError:
            return
        else:
            handler(presence)

    def _onPresenceAvailable(self, presence):
        entity = JID(presence["from"])

        show = unicode(presence.show or '')
        if show not in ['away', 'xa', 'chat', 'dnd']:
            show = None

        statuses = self._getStatuses(presence)

        try:
            priority = int(unicode(presence.priority or '')) or 0
        except ValueError:
            priority = 0

        self.availableReceived(entity, show, statuses, priority)

    def _onPresenceUnavailable(self, presence):
        entity = JID(presence["from"])

        statuses = self._getStatuses(presence)

        self.unavailableReceived(entity, statuses)

    def _onPresenceSubscribed(self, presence):
        self.subscribedReceived(JID(presence["from"]))

    def _onPresenceUnsubscribed(self, presence):
        self.unsubscribedReceived(JID(presence["from"]))

    def _onPresenceSubscribe(self, presence):
        self.subscribeReceived(JID(presence["from"]))

    def _onPresenceUnsubscribe(self, presence):
        self.unsubscribeReceived(JID(presence["from"]))

    def availableReceived(self, entity, show=None, statuses=None, priority=0):
        """
        Available presence was received.

        @param entity: entity from which the presence was received.
        @type entity: {JID}
        @param show: detailed presence information. One of C{'away'}, C{'xa'},
                     C{'chat'}, C{'dnd'} or C{None}.
        @type show: C{str} or C{NoneType}
        @param statuses: dictionary of natural language descriptions of the
                         availability status, keyed by the language
                         descriptor. A status without a language
                         specified, is keyed with C{None}.
        @type statuses: C{dict}
        @param priority: priority level of the resource.
        @type priority: C{int}
        """

    def unavailableReceived(self, entity, statuses=None):
        """
        Unavailable presence was received.

        @param entity: entity from which the presence was received.
        @type entity: {JID}
        @param statuses: dictionary of natural language descriptions of the
                         availability status, keyed by the language
                         descriptor. A status without a language
                         specified, is keyed with C{None}.
        @type statuses: C{dict}
        """

    def subscribedReceived(self, entity):
        """
        Subscription approval confirmation was received.

        @param entity: entity from which the confirmation was received.
        @type entity: {JID}
        """

    def unsubscribedReceived(self, entity):
        """
        Unsubscription confirmation was received.

        @param entity: entity from which the confirmation was received.
        @type entity: {JID}
        """

    def subscribeReceived(self, entity):
        """
        Subscription request was received.

        @param entity: entity from which the request was received.
        @type entity: {JID}
        """

    def unsubscribeReceived(self, entity):
        """
        Unsubscription request was received.

        @param entity: entity from which the request was received.
        @type entity: {JID}
        """

    def available(self, entity=None, show=None, statuses=None, priority=0):
        """
        Send available presence.

        @param entity: optional entity to which the presence should be sent.
        @type entity: {JID}
        @param show: optional detailed presence information. One of C{'away'},
                     C{'xa'}, C{'chat'}, C{'dnd'}.
        @type show: C{str}
        @param statuses: dictionary of natural language descriptions of the
                         availability status, keyed by the language
                         descriptor. A status without a language
                         specified, is keyed with C{None}.
        @type statuses: C{dict}
        @param priority: priority level of the resource.
        @type priority: C{int}
        """
        self.send(AvailablePresence(entity, show, statuses, priority))

    def unavailable(self, entity=None, statuses=None):
        """
        Send unavailable presence.

        @param entity: optional entity to which the presence should be sent.
        @type entity: {JID}
        @param statuses: dictionary of natural language descriptions of the
                         availability status, keyed by the language
                         descriptor. A status without a language
                         specified, is keyed with C{None}.
        @type statuses: C{dict}
        """
        self.send(UnavailablePresence(entity, statuses))

    def subscribe(self, entity):
        """
        Send subscription request

        @param entity: entity to subscribe to.
        @type entity: {JID}
        """
        self.send(Presence(to=entity, type='subscribe'))

    def unsubscribe(self, entity):
        """
        Send unsubscription request

        @param entity: entity to unsubscribe from.
        @type entity: {JID}
        """
        self.send(Presence(to=entity, type='unsubscribe'))

    def subscribed(self, entity):
        """
        Send subscription confirmation.

        @param entity: entity that subscribed.
        @type entity: {JID}
        """
        self.send(Presence(to=entity, type='subscribed'))

    def unsubscribed(self, entity):
        """
        Send unsubscription confirmation.

        @param entity: entity that unsubscribed.
        @type entity: {JID}
        """
        self.send(Presence(to=entity, type='unsubscribed'))


class RosterItem(object):
    """
    Roster item.

    This represents one contact from an XMPP contact list known as roster.

    @ivar jid: The JID of the contact.
    @type jid: L{JID}
    @ivar name: The optional associated nickname for this contact.
    @type name: C{unicode}
    @ivar subscriptionTo: Subscription state to contact's presence. If C{True},
                          the roster owner is subscribed to the presence
                          information of the contact.
    @type subscriptionTo: C{bool}
    @ivar subscriptionFrom: Contact's subscription state. If C{True}, the
                            contact is subscribed to the presence information
                            of the roster owner.
    @type subscriptionTo: C{bool}
    @ivar ask: Whether subscription is pending.
    @type ask: C{bool}
    @ivar groups: Set of groups this contact is categorized in. Groups are
                  represented by an opaque identifier of type C{unicode}.
    @type groups: C{set}
    """

    def __init__(self, jid):
        self.jid = jid
        self.name = None
        self.subscriptionTo = False
        self.subscriptionFrom = False
        self.ask = None
        self.groups = set()


class RosterClientProtocol(XMPPHandler):
    """
    Client side XMPP roster protocol.
    """

    def connectionInitialized(self):
        ROSTER_SET = "/iq[@type='set']/query[@xmlns='%s']" % NS_ROSTER
        self.xmlstream.addObserver(ROSTER_SET, self._onRosterSet)

    def _parseRosterItem(self, element):
        jid = JID(element['jid'])
        item = RosterItem(jid)
        item.name = element.getAttribute('name')
        subscription = element.getAttribute('subscription')
        item.subscriptionTo = subscription in ('to', 'both')
        item.subscriptionFrom = subscription in ('from', 'both')
        item.ask = element.getAttribute('ask') == 'subscribe'
        for subElement in domish.generateElementsQNamed(element.children,
                                                        'group', NS_ROSTER):
            item.groups.add(unicode(subElement))

        return item

    def getRoster(self):
        """
        Retrieve contact list.

        @return: Roster as a mapping from L{JID} to L{RosterItem}.
        @rtype: L{twisted.internet.defer.Deferred}
        """

        def processRoster(result):
            roster = {}
            for element in domish.generateElementsQNamed(result.query.children,
                                                         'item', NS_ROSTER):
                item = self._parseRosterItem(element)
                roster[item.jid.userhost()] = item

            return roster

        iq = IQ(self.xmlstream, 'get')
        iq.addElement((NS_ROSTER, 'query'))
        d = iq.send()
        d.addCallback(processRoster)
        return d


    def removeItem(self, entity):
        """
        Remove an item from the contact list.

        @param entity: The contact to remove the roster item for.
        @type entity: L{JID<twisted.words.protocols.jabber.jid.JID>}
        @rtype: L{twisted.internet.defer.Deferred}
        """
        iq = IQ(self.xmlstream, 'set')
        iq.addElement((NS_ROSTER, 'query'))
        item = iq.query.addElement('item')
        item['jid'] = entity.full()
        item['subscription'] = 'remove'
        return iq.send()


    def _onRosterSet(self, iq):
        if iq.handled or \
           iq.hasAttribute('from') and iq['from'] != self.xmlstream:
            return

        iq.handled = True

        itemElement = iq.query.item

        if unicode(itemElement['subscription']) == 'remove':
            self.onRosterRemove(JID(itemElement['jid']))
        else:
            item = self._parseRosterItem(iq.query.item)
            self.onRosterSet(item)

    def onRosterSet(self, item):
        """
        Called when a roster push for a new or update item was received.

        @param item: The pushed roster item.
        @type item: L{RosterItem}
        """

    def onRosterRemove(self, entity):
        """
        Called when a roster push for the removal of an item was received.

        @param entity: The entity for which the roster item has been removed.
        @type entity: L{JID}
        """

class MessageProtocol(XMPPHandler):
    """
    Generic XMPP subprotocol handler for incoming message stanzas.
    """

    messageTypes = None, 'normal', 'chat', 'headline', 'groupchat'

    def connectionInitialized(self):
        self.xmlstream.addObserver("/message", self._onMessage)

    def _onMessage(self, message):
        if message.handled:
            return

        messageType = message.getAttribute("type")

        if messageType == 'error':
            return

        if messageType not in self.messageTypes:
            message["type"] = 'normal'

        self.onMessage(message)

    def onMessage(self, message):
        """
        Called when a message stanza was received.
        """
