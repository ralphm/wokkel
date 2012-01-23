# -*- test-case-name: wokkel.test.test_xmppim -*-
#
# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
XMPP IM protocol support.

This module provides generic implementations for the protocols defined in
U{RFC 3921<http://xmpp.org/rfcs/rfc3921.html>} (XMPP IM).

All of it should eventually move to Twisted.
"""

from twisted.words.protocols.jabber.jid import JID
from twisted.words.xish import domish

from wokkel.compat import IQ
from wokkel.generic import ErrorStanza, Stanza
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



class BasePresence(Stanza):
    """
    Stanza of kind presence.
    """
    stanzaKind = 'presence'



class AvailabilityPresence(BasePresence):
    """
    Presence.

    This represents availability presence (as opposed to
    L{SubscriptionPresence}).

    @ivar available: The availability being communicated.
    @type available: C{bool}
    @ivar show: More specific availability. Can be one of C{'chat'}, C{'away'},
                C{'xa'}, C{'dnd'} or C{None}.
    @type show: C{str} or C{NoneType}
    @ivar statuses: Natural language texts to detail the (un)availability.
                    These are represented as a mapping from language code
                    (C{str} or C{None}) to the corresponding text (C{unicode}).
                    If the key is C{None}, the associated text is in the
                    default language.
    @type statuses: C{dict}
    @ivar priority: Priority level for this resource. Must be between -128 and
                    127. Defaults to 0.
    @type priority: C{int}
    """

    childParsers = {(None, 'show'): '_childParser_show',
                     (None, 'status'): '_childParser_status',
                     (None, 'priority'): '_childParser_priority'}

    def __init__(self, recipient=None, sender=None, available=True,
                       show=None, status=None, statuses=None, priority=0):
        BasePresence.__init__(self, recipient=recipient, sender=sender)
        self.available = available
        self.show = show
        self.statuses = statuses or {}
        if status:
            self.statuses[None] = status
        self.priority = priority


    def __get_status(self):
        if None in self.statuses:
            return self.statuses[None]
        elif self.statuses:
            for status in self.status.itervalues():
                return status
        else:
            return None

    status = property(__get_status)


    def _childParser_show(self, element):
        show = unicode(element)
        if show in ('chat', 'away', 'xa', 'dnd'):
            self.show = show


    def _childParser_status(self, element):
        lang = element.getAttribute((NS_XML, 'lang'), None)
        text = unicode(element)
        self.statuses[lang] = text


    def _childParser_priority(self, element):
        try:
            self.priority = int(unicode(element))
        except ValueError:
            pass


    def parseElement(self, element):
        BasePresence.parseElement(self, element)

        if self.stanzaType == 'unavailable':
            self.available = False


    def toElement(self):
        if not self.available:
            self.stanzaType = 'unavailable'

        presence = BasePresence.toElement(self)

        if self.available:
            if self.show in ('chat', 'away', 'xa', 'dnd'):
                presence.addElement('show', content=self.show)
            if self.priority != 0:
                presence.addElement('priority', content=unicode(self.priority))

        for lang, text in self.statuses.iteritems():
            status = presence.addElement('status', content=text)
            if lang:
                status[(NS_XML, 'lang')] = lang

        return presence



class SubscriptionPresence(BasePresence):
    """
    Presence subscription request or response.

    This kind of presence is used to represent requests for presence
    subscription and their replies.

    Based on L{BasePresence} and {Stanza}, it just uses the C{stanzaType}
    attribute to represent the type of subscription presence. This can be
    one of C{'subscribe'}, C{'unsubscribe'}, C{'subscribed'} and
    C{'unsubscribed'}.
    """



class ProbePresence(BasePresence):
    """
    Presence probe request.
    """

    stanzaType = 'probe'



class BasePresenceProtocol(XMPPHandler):
    """
    XMPP Presence base protocol handler.

    This class is the base for protocol handlers that receive presence
    stanzas. Listening to all incoming presence stanzas, it extracts the
    stanza's type and looks up a matching stanza parser and calls the
    associated method. The method's name is the type + C{Received}. E.g.
    C{availableReceived}. See L{PresenceProtocol} for a complete example.

    @cvar presenceTypeParserMap: Maps presence stanza types to their respective
        stanza parser classes (derived from L{Stanza}).
    @type presenceTypeParserMap: C{dict}
    """

    presenceTypeParserMap = {}

    def connectionInitialized(self):
        self.xmlstream.addObserver("/presence", self._onPresence)



    def _onPresence(self, element):
        """
        Called when a presence stanza has been received.
        """
        stanza = Stanza.fromElement(element)

        presenceType = stanza.stanzaType or 'available'

        try:
            parser = self.presenceTypeParserMap[presenceType]
        except KeyError:
            return

        presence = parser.fromElement(element)

        try:
            handler = getattr(self, '%sReceived' % presenceType)
        except AttributeError:
            return
        else:
            handler(presence)



class PresenceProtocol(BasePresenceProtocol):

    presenceTypeParserMap = {
                'error': ErrorStanza,
                'available': AvailabilityPresence,
                'unavailable': AvailabilityPresence,
                'subscribe': SubscriptionPresence,
                'unsubscribe': SubscriptionPresence,
                'subscribed': SubscriptionPresence,
                'unsubscribed': SubscriptionPresence,
                'probe': ProbePresence,
                }


    def errorReceived(self, presence):
        """
        Error presence was received.
        """
        pass


    def availableReceived(self, presence):
        """
        Available presence was received.
        """
        pass


    def unavailableReceived(self, presence):
        """
        Unavailable presence was received.
        """
        pass


    def subscribedReceived(self, presence):
        """
        Subscription approval confirmation was received.
        """
        pass


    def unsubscribedReceived(self, presence):
        """
        Unsubscription confirmation was received.
        """
        pass


    def subscribeReceived(self, presence):
        """
        Subscription request was received.
        """
        pass


    def unsubscribeReceived(self, presence):
        """
        Unsubscription request was received.
        """
        pass


    def probeReceived(self, presence):
        """
        Probe presence was received.
        """
        pass


    def available(self, recipient=None, show=None, statuses=None, priority=0,
                        status=None, sender=None):
        """
        Send available presence.

        @param recipient: Optional Recipient to which the presence should be
            sent.
        @type recipient: {JID}

        @param show: Optional detailed presence information. One of C{'away'},
            C{'xa'}, C{'chat'}, C{'dnd'}.
        @type show: C{str}

        @param statuses: Mapping of natural language descriptions of the
           availability status, keyed by the language descriptor. A status
           without a language specified, is keyed with C{None}.
        @type statuses: C{dict}

        @param priority: priority level of the resource.
        @type priority: C{int}
        """
        presence = AvailabilityPresence(recipient=recipient, sender=sender,
                                        show=show, statuses=statuses,
                                        status=status, priority=priority)
        self.send(presence.toElement())


    def unavailable(self, recipient=None, statuses=None, sender=None):
        """
        Send unavailable presence.

        @param recipient: Optional entity to which the presence should be sent.
        @type recipient: {JID}

        @param statuses: dictionary of natural language descriptions of the
            availability status, keyed by the language descriptor. A status
            without a language specified, is keyed with C{None}.
        @type statuses: C{dict}
        """
        presence = AvailabilityPresence(recipient=recipient, sender=sender,
                                        available=False, statuses=statuses)
        self.send(presence.toElement())


    def subscribe(self, recipient, sender=None):
        """
        Send subscription request

        @param recipient: Entity to subscribe to.
        @type recipient: {JID}
        """
        presence = SubscriptionPresence(recipient=recipient, sender=sender)
        presence.stanzaType = 'subscribe'
        self.send(presence.toElement())


    def unsubscribe(self, recipient, sender=None):
        """
        Send unsubscription request

        @param recipient: Entity to unsubscribe from.
        @type recipient: {JID}
        """
        presence = SubscriptionPresence(recipient=recipient, sender=sender)
        presence.stanzaType = 'unsubscribe'
        self.send(presence.toElement())


    def subscribed(self, recipient, sender=None):
        """
        Send subscription confirmation.

        @param recipient: Entity that subscribed.
        @type recipient: {JID}
        """
        presence = SubscriptionPresence(recipient=recipient, sender=sender)
        presence.stanzaType = 'subscribed'
        self.send(presence.toElement())


    def unsubscribed(self, recipient, sender=None):
        """
        Send unsubscription confirmation.

        @param recipient: Entity that unsubscribed.
        @type recipient: {JID}
        """
        presence = SubscriptionPresence(recipient=recipient, sender=sender)
        presence.stanzaType = 'unsubscribed'
        self.send(presence.toElement())


    def probe(self, recipient, sender=None):
        """
        Send presence probe.

        @param recipient: Entity to be probed.
        @type recipient: {JID}
        """
        presence = ProbePresence(recipient=recipient, sender=sender)
        self.send(presence.toElement())



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



class Message(Stanza):
    """
    A message stanza.
    """

    stanzaKind = 'message'

    childParsers = {
            (None, 'body'): '_childParser_body',
            (None, 'subject'): '_childParser_subject',
            }

    def __init__(self, recipient=None, sender=None, body=None, subject=None):
        Stanza.__init__(self, recipient, sender)
        self.body = body
        self.subject = subject


    def _childParser_body(self, element):
        self.body = unicode(element)


    def _childParser_subject(self, element):
        self.subject = unicode(element)


    def toElement(self):
        element = Stanza.toElement(self)

        if self.body:
            element.addElement('body', content=self.body)
        if self.subject:
            element.addElement('subject', content=self.subject)

        return element



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
