# -*- test-case-name: wokkel.test.test_pubsub -*-
#
# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
XMPP publish-subscribe protocol.

This protocol is specified in
U{XEP-0060<http://xmpp.org/extensions/xep-0060.html>}.
"""

from __future__ import division, absolute_import

from zope.interface import implementer

from twisted.internet import defer
from twisted.python import log
from twisted.python.compat import StringType, iteritems, unicode
from twisted.words.protocols.jabber import jid, error
from twisted.words.xish import domish

from wokkel import disco, data_form, generic, shim
from wokkel.compat import IQ
from wokkel.subprotocols import IQHandlerMixin, XMPPHandler
from wokkel.iwokkel import IPubSubClient, IPubSubService, IPubSubResource

# Iq get and set XPath queries
IQ_GET = '/iq[@type="get"]'
IQ_SET = '/iq[@type="set"]'

# Publish-subscribe namespaces
NS_PUBSUB = 'http://jabber.org/protocol/pubsub'
NS_PUBSUB_EVENT = NS_PUBSUB + '#event'
NS_PUBSUB_ERRORS = NS_PUBSUB + '#errors'
NS_PUBSUB_OWNER = NS_PUBSUB + "#owner"
NS_PUBSUB_NODE_CONFIG = NS_PUBSUB + "#node_config"
NS_PUBSUB_META_DATA = NS_PUBSUB + "#meta-data"
NS_PUBSUB_SUBSCRIBE_OPTIONS = NS_PUBSUB + "#subscribe_options"

# XPath to match pubsub requests
PUBSUB_REQUEST = '/iq[@type="get" or @type="set"]/' + \
                    'pubsub[@xmlns="' + NS_PUBSUB + '" or ' + \
                           '@xmlns="' + NS_PUBSUB_OWNER + '"]'

class SubscriptionPending(Exception):
    """
    Raised when the requested subscription is pending acceptance.
    """



class SubscriptionUnconfigured(Exception):
    """
    Raised when the requested subscription needs to be configured before
    becoming active.
    """



class PubSubError(error.StanzaError):
    """
    Exception with publish-subscribe specific condition.
    """
    def __init__(self, condition, pubsubCondition, feature=None, text=None):
        appCondition = domish.Element((NS_PUBSUB_ERRORS, pubsubCondition))
        if feature:
            appCondition['feature'] = feature
        error.StanzaError.__init__(self, condition,
                                         text=text,
                                         appCondition=appCondition)



class BadRequest(error.StanzaError):
    """
    Bad request stanza error.
    """
    def __init__(self, pubsubCondition=None, text=None):
        if pubsubCondition:
            appCondition = domish.Element((NS_PUBSUB_ERRORS, pubsubCondition))
        else:
            appCondition = None
        error.StanzaError.__init__(self, 'bad-request',
                                         text=text,
                                         appCondition=appCondition)



class Unsupported(PubSubError):
    def __init__(self, feature, text=None):
        self.feature = feature
        PubSubError.__init__(self, 'feature-not-implemented',
                                   'unsupported',
                                   feature,
                                   text)

    def __str__(self):
        message = PubSubError.__str__(self)
        message += ', feature %r' % self.feature
        return message


class Subscription(object):
    """
    A subscription to a node.

    @ivar nodeIdentifier: The identifier of the node subscribed to.  The root
        node is denoted by L{None}.
    @type nodeIdentifier: L{unicode}

    @ivar subscriber: The subscribing entity.
    @type subscriber: L{jid.JID}

    @ivar state: The subscription state. One of C{'subscribed'}, C{'pending'},
                 C{'unconfigured'}.
    @type state: L{unicode}

    @ivar options: Optional list of subscription options.
    @type options: L{dict}

    @ivar subscriptionIdentifier: Optional subscription identifier.
    @type subscriptionIdentifier: L{unicode}
    """

    def __init__(self, nodeIdentifier, subscriber, state, options=None,
                       subscriptionIdentifier=None):
        self.nodeIdentifier = nodeIdentifier
        self.subscriber = subscriber
        self.state = state
        self.options = options or {}
        self.subscriptionIdentifier = subscriptionIdentifier


    @staticmethod
    def fromElement(element):
        return Subscription(
                element.getAttribute('node'),
                jid.JID(element.getAttribute('jid')),
                element.getAttribute('subscription'),
                subscriptionIdentifier=element.getAttribute('subid'))


    def toElement(self, defaultUri=None):
        """
        Return the DOM representation of this subscription.

        @rtype: L{domish.Element}
        """
        element = domish.Element((defaultUri, 'subscription'))
        if self.nodeIdentifier:
            element['node'] = self.nodeIdentifier
        element['jid'] = unicode(self.subscriber)
        element['subscription'] = self.state
        if self.subscriptionIdentifier:
            element['subid'] = self.subscriptionIdentifier
        return element



class Item(domish.Element):
    """
    Publish subscribe item.

    This behaves like an object providing L{domish.IElement}.

    Item payload can be added using C{addChild} or C{addRawXml}, or using the
    C{payload} keyword argument to C{__init__}.
    """

    def __init__(self, id=None, payload=None):
        """
        @param id: optional item identifier
        @type id: L{unicode}
        @param payload: optional item payload. Either as a domish element, or
                        as serialized XML.
        @type payload: object providing L{domish.IElement} or L{unicode}.
        """

        domish.Element.__init__(self, (None, 'item'))
        if id is not None:
            self['id'] = id
        if payload is not None:
            if isinstance(payload, StringType):
                self.addRawXml(payload)
            else:
                self.addChild(payload)



class PubSubRequest(generic.Stanza):
    """
    A publish-subscribe request.

    The set of instance variables used depends on the type of request. If
    a variable is not applicable or not passed in the request, its value is
    L{None}.

    @ivar verb: The type of publish-subscribe request. See C{_requestVerbMap}.
    @type verb: L{str}.

    @ivar affiliations: Affiliations to be modified.
    @type affiliations: L{set}

    @ivar items: The items to be published, as L{domish.Element}s.
    @type items: L{list}

    @ivar itemIdentifiers: Identifiers of the items to be retrieved or
                           retracted.
    @type itemIdentifiers: L{set}

    @ivar maxItems: Maximum number of items to retrieve.
    @type maxItems: L{int}.

    @ivar nodeIdentifier: Identifier of the node the request is about.
    @type nodeIdentifier: L{unicode}

    @ivar nodeType: The type of node that should be created, or for which the
                    configuration is retrieved. C{'leaf'} or C{'collection'}.
    @type nodeType: L{str}

    @ivar options: Configurations options for nodes, subscriptions and publish
                   requests.
    @type options: L{data_form.Form}

    @ivar subscriber: The subscribing entity.
    @type subscriber: L{JID<twisted.words.protocols.jabber.jid.JID>}

    @ivar subscriptionIdentifier: Identifier for a specific subscription.
    @type subscriptionIdentifier: L{unicode}

    @ivar subscriptions: Subscriptions to be modified, as a set of
        L{Subscription}.
    @type subscriptions: L{set}

    @ivar affiliations: Affiliations to be modified, as a dictionary of entity
        (L{JID<twisted.words.protocols.jabber.jid.JID>} to affiliation
        (L{unicode}).
    @type affiliations: L{dict}
    """

    verb = None

    affiliations = None
    items = None
    itemIdentifiers = None
    maxItems = None
    nodeIdentifier = None
    nodeType = None
    options = None
    subscriber = None
    subscriptionIdentifier = None
    subscriptions = None
    affiliations = None

    # Map request iq type and subelement name to request verb
    _requestVerbMap = {
        ('set', NS_PUBSUB, 'publish'): 'publish',
        ('set', NS_PUBSUB, 'subscribe'): 'subscribe',
        ('set', NS_PUBSUB, 'unsubscribe'): 'unsubscribe',
        ('get', NS_PUBSUB, 'options'): 'optionsGet',
        ('set', NS_PUBSUB, 'options'): 'optionsSet',
        ('get', NS_PUBSUB, 'subscriptions'): 'subscriptions',
        ('get', NS_PUBSUB, 'affiliations'): 'affiliations',
        ('set', NS_PUBSUB, 'create'): 'create',
        ('get', NS_PUBSUB_OWNER, 'default'): 'default',
        ('get', NS_PUBSUB_OWNER, 'configure'): 'configureGet',
        ('set', NS_PUBSUB_OWNER, 'configure'): 'configureSet',
        ('get', NS_PUBSUB, 'items'): 'items',
        ('set', NS_PUBSUB, 'retract'): 'retract',
        ('set', NS_PUBSUB_OWNER, 'purge'): 'purge',
        ('set', NS_PUBSUB_OWNER, 'delete'): 'delete',
        ('get', NS_PUBSUB_OWNER, 'affiliations'): 'affiliationsGet',
        ('set', NS_PUBSUB_OWNER, 'affiliations'): 'affiliationsSet',
        ('get', NS_PUBSUB_OWNER, 'subscriptions'): 'subscriptionsGet',
        ('set', NS_PUBSUB_OWNER, 'subscriptions'): 'subscriptionsSet',
    }

    # Map request verb to request iq type and subelement name
    _verbRequestMap = dict(((v, k) for k, v in iteritems(_requestVerbMap)))

    # Map request verb to parameter handler names
    _parameters = {
        'publish': ['node', 'items'],
        'subscribe': ['nodeOrEmpty', 'jid', 'optionsWithSubscribe'],
        'unsubscribe': ['nodeOrEmpty', 'jid', 'subidOrNone'],
        'optionsGet': ['nodeOrEmpty', 'jid', 'subidOrNone'],
        'optionsSet': ['nodeOrEmpty', 'jid', 'options', 'subidOrNone'],
        'subscriptions': [],
        'affiliations': [],
        'create': ['nodeOrNone', 'configureOrNone'],
        'default': ['default'],
        'configureGet': ['nodeOrEmpty'],
        'configureSet': ['nodeOrEmpty', 'configure'],
        'items': ['node', 'maxItems', 'itemIdentifiers', 'subidOrNone'],
        'retract': ['node', 'itemIdentifiers'],
        'purge': ['node'],
        'delete': ['node'],
        'affiliationsGet': ['nodeOrEmpty'],
        'affiliationsSet': ['nodeOrEmpty', 'affiliations'],
        'subscriptionsGet': ['nodeOrEmpty'],
        'subscriptionsSet': [],
    }

    def __init__(self, verb=None):
        self.verb = verb


    def _parse_node(self, verbElement):
        """
        Parse the required node identifier out of the verbElement.
        """
        try:
            self.nodeIdentifier = verbElement["node"]
        except KeyError:
            raise BadRequest('nodeid-required')


    def _render_node(self, verbElement):
        """
        Render the required node identifier on the verbElement.
        """
        if not self.nodeIdentifier:
            raise Exception("Node identifier is required")

        verbElement['node'] = self.nodeIdentifier


    def _parse_nodeOrEmpty(self, verbElement):
        """
        Parse the node identifier out of the verbElement. May be empty.
        """
        self.nodeIdentifier = verbElement.getAttribute("node", '')


    def _render_nodeOrEmpty(self, verbElement):
        """
        Render the node identifier on the verbElement. May be empty.
        """
        if self.nodeIdentifier:
            verbElement['node'] = self.nodeIdentifier


    def _parse_nodeOrNone(self, verbElement):
        """
        Parse the optional node identifier out of the verbElement.
        """
        self.nodeIdentifier = verbElement.getAttribute("node")


    def _render_nodeOrNone(self, verbElement):
        """
        Render the optional node identifier on the verbElement.
        """
        if self.nodeIdentifier:
            verbElement['node'] = self.nodeIdentifier


    def _parse_items(self, verbElement):
        """
        Parse items out of the verbElement for publish requests.
        """
        self.items = []
        for element in verbElement.elements():
            if element.uri == NS_PUBSUB and element.name == 'item':
                self.items.append(element)


    def _render_items(self, verbElement):
        """
        Render items into the verbElement for publish requests.
        """
        if self.items:
            for item in self.items:
                item.uri = NS_PUBSUB
                verbElement.addChild(item)


    def _parse_jid(self, verbElement):
        """
        Parse subscriber out of the verbElement for un-/subscribe requests.
        """
        try:
            self.subscriber = jid.internJID(verbElement["jid"])
        except KeyError:
            raise BadRequest('jid-required')


    def _render_jid(self, verbElement):
        """
        Render subscriber into the verbElement for un-/subscribe requests.
        """
        verbElement['jid'] = self.subscriber.full()


    def _parse_default(self, verbElement):
        """
        Parse node type out of a request for the default node configuration.
        """
        form = data_form.findForm(verbElement, NS_PUBSUB_NODE_CONFIG)
        if form is not None and form.formType == 'submit':
            values = form.getValues()
            self.nodeType = values.get('pubsub#node_type', 'leaf')
        else:
            self.nodeType = 'leaf'


    def _parse_configure(self, verbElement):
        """
        Parse options out of a request for setting the node configuration.
        """
        form = data_form.findForm(verbElement, NS_PUBSUB_NODE_CONFIG)
        if form is not None:
            if form.formType in ('submit', 'cancel'):
                self.options = form
            else:
                raise BadRequest(text=u"Unexpected form type '%s'" % form.formType)
        else:
            raise BadRequest(text="Missing configuration form")


    def _parse_configureOrNone(self, verbElement):
        """
        Parse optional node configuration form in create request.
        """
        for element in verbElement.parent.elements():
            if element.uri == NS_PUBSUB and element.name == 'configure':
                form = data_form.findForm(element, NS_PUBSUB_NODE_CONFIG)
                if form is not None:
                    if form.formType != 'submit':
                        raise BadRequest(text=u"Unexpected form type '%s'" %
                                              form.formType)
                else:
                    form = data_form.Form('submit',
                                          formNamespace=NS_PUBSUB_NODE_CONFIG)
                self.options = form


    def _render_configureOrNone(self, verbElement):
        """
        Render optional node configuration form in create request.
        """
        if self.options is not None:
            configure = verbElement.parent.addElement('configure')
            configure.addChild(self.options.toElement())


    def _parse_itemIdentifiers(self, verbElement):
        """
        Parse item identifiers out of items and retract requests.
        """
        self.itemIdentifiers = []
        for element in verbElement.elements():
            if element.uri == NS_PUBSUB and element.name == 'item':
                try:
                    self.itemIdentifiers.append(element["id"])
                except KeyError:
                    raise BadRequest()


    def _render_itemIdentifiers(self, verbElement):
        """
        Render item identifiers into items and retract requests.
        """
        if self.itemIdentifiers:
            for itemIdentifier in self.itemIdentifiers:
                item = verbElement.addElement('item')
                item['id'] = itemIdentifier


    def _parse_maxItems(self, verbElement):
        """
        Parse maximum items out of an items request.
        """
        value = verbElement.getAttribute('max_items')

        if value:
            try:
                self.maxItems = int(value)
            except ValueError:
                raise BadRequest(text="Field max_items requires a positive " +
                                      "integer value")


    def _render_maxItems(self, verbElement):
        """
        Render maximum items into an items request.
        """
        if self.maxItems:
            verbElement['max_items'] = unicode(self.maxItems)


    def _parse_subidOrNone(self, verbElement):
        """
        Parse subscription identifier out of a request.
        """
        self.subscriptionIdentifier = verbElement.getAttribute("subid")


    def _render_subidOrNone(self, verbElement):
        """
        Render subscription identifier into a request.
        """
        if self.subscriptionIdentifier:
            verbElement['subid'] = self.subscriptionIdentifier


    def _parse_options(self, verbElement):
        """
        Parse options form out of a subscription options request.
        """
        form = data_form.findForm(verbElement, NS_PUBSUB_SUBSCRIBE_OPTIONS)
        if form is not None:
            if form.formType in ('submit', 'cancel'):
                self.options = form
            else:
                raise BadRequest(text=u"Unexpected form type '%s'" % form.formType)
        else:
            raise BadRequest(text="Missing options form")



    def _render_options(self, verbElement):
        verbElement.addChild(self.options.toElement())


    def _parse_optionsWithSubscribe(self, verbElement):
        for element in verbElement.parent.elements():
            if element.name == 'options' and element.uri == NS_PUBSUB:
                form = data_form.findForm(element,
                                          NS_PUBSUB_SUBSCRIBE_OPTIONS)
                if form is not None:
                    if form.formType != 'submit':
                        raise BadRequest(text=u"Unexpected form type '%s'" %
                                              form.formType)
                else:
                    form = data_form.Form('submit',
                                          formNamespace=NS_PUBSUB_SUBSCRIBE_OPTIONS)
                self.options = form


    def _render_optionsWithSubscribe(self, verbElement):
        if self.options is not None:
            optionsElement = verbElement.parent.addElement('options')
            self._render_options(optionsElement)


    def _parse_affiliations(self, verbElement):
        self.affiliations = {}
        for element in verbElement.elements():
            if (element.uri == NS_PUBSUB_OWNER and
                element.name == 'affiliation'):
                try:
                    entity = jid.internJID(element['jid']).userhostJID()
                except KeyError:
                    raise BadRequest(text='Missing jid attribute')

                if entity in self.affiliations:
                    raise BadRequest(text='Multiple affiliations for an entity')

                try:
                    affiliation = element['affiliation']
                except KeyError:
                    raise BadRequest(text='Missing affiliation attribute')

                self.affiliations[entity] = affiliation


    def parseElement(self, element):
        """
        Parse the publish-subscribe verb and parameters out of a request.
        """
        generic.Stanza.parseElement(self, element)

        verbs = []
        verbElements = []
        for child in element.pubsub.elements():
            key = (self.stanzaType, child.uri, child.name)
            try:
                verb = self._requestVerbMap[key]
            except KeyError:
                continue

            verbs.append(verb)
            verbElements.append(child)

        if not verbs:
            raise NotImplementedError()

        if len(verbs) > 1:
            if 'optionsSet' in verbs and 'subscribe' in verbs:
                self.verb = 'subscribe'
                verbElement = verbElements[verbs.index('subscribe')]
            else:
                raise NotImplementedError()
        else:
            self.verb = verbs[0]
            verbElement = verbElements[0]

        for parameter in self._parameters[self.verb]:
            getattr(self, '_parse_%s' % parameter)(verbElement)



    def send(self, xs):
        """
        Send this request to its recipient.

        This renders all of the relevant parameters for this specific
        requests into an L{IQ}, and invoke its C{send} method.
        This returns a deferred that fires upon reception of a response. See
        L{IQ} for details.

        @param xs: The XML stream to send the request on.
        @type xs: L{twisted.words.protocols.jabber.xmlstream.XmlStream}
        @rtype: L{defer.Deferred}.
        """

        try:
            (self.stanzaType,
             childURI,
             childName) = self._verbRequestMap[self.verb]
        except KeyError:
            raise NotImplementedError()

        iq = IQ(xs, self.stanzaType)
        iq.addElement((childURI, 'pubsub'))
        verbElement = iq.pubsub.addElement(childName)

        if self.sender:
            iq['from'] = self.sender.full()
        if self.recipient:
            iq['to'] = self.recipient.full()

        for parameter in self._parameters[self.verb]:
            getattr(self, '_render_%s' % parameter)(verbElement)

        return iq.send()



class PubSubEvent(object):
    """
    A publish subscribe event.

    @param sender: The entity from which the notification was received.
    @type sender: L{jid.JID}
    @param recipient: The entity to which the notification was sent.
    @type recipient: L{wokkel.pubsub.ItemsEvent}
    @param nodeIdentifier: Identifier of the node the event pertains to.
    @type nodeIdentifier: L{unicode}
    @param headers: SHIM headers, see L{wokkel.shim.extractHeaders}.
    @type headers: L{dict}
    """

    def __init__(self, sender, recipient, nodeIdentifier, headers):
        self.sender = sender
        self.recipient = recipient
        self.nodeIdentifier = nodeIdentifier
        self.headers = headers



class ItemsEvent(PubSubEvent):
    """
    A publish-subscribe event that signifies new, updated and retracted items.

    @param items: List of received items as domish elements.
    @type items: L{list} of L{domish.Element}
    """

    def __init__(self, sender, recipient, nodeIdentifier, items, headers):
        PubSubEvent.__init__(self, sender, recipient, nodeIdentifier, headers)
        self.items = items



class DeleteEvent(PubSubEvent):
    """
    A publish-subscribe event that signifies the deletion of a node.
    """

    redirectURI = None



class PurgeEvent(PubSubEvent):
    """
    A publish-subscribe event that signifies the purging of a node.
    """



@implementer(IPubSubClient)
class PubSubClient(XMPPHandler):
    """
    Publish subscribe client protocol.
    """

    def connectionInitialized(self):
        self.xmlstream.addObserver('/message/event[@xmlns="%s"]' %
                                   NS_PUBSUB_EVENT, self._onEvent)


    def _onEvent(self, message):
        if message.getAttribute('type') == 'error':
            return

        try:
            sender = jid.JID(message["from"])
            recipient = jid.JID(message["to"])
        except KeyError:
            return

        actionElement = None
        for element in message.event.elements():
            if element.uri == NS_PUBSUB_EVENT:
                actionElement = element

        if not actionElement:
            return

        eventHandler = getattr(self, "_onEvent_%s" % actionElement.name, None)

        if eventHandler:
            headers = shim.extractHeaders(message)
            eventHandler(sender, recipient, actionElement, headers)
            message.handled = True


    def _onEvent_items(self, sender, recipient, action, headers):
        nodeIdentifier = action["node"]

        items = [element for element in action.elements()
                         if element.name in ('item', 'retract')]

        event = ItemsEvent(sender, recipient, nodeIdentifier, items, headers)
        self.itemsReceived(event)


    def _onEvent_delete(self, sender, recipient, action, headers):
        nodeIdentifier = action["node"]
        event = DeleteEvent(sender, recipient, nodeIdentifier, headers)
        if action.redirect:
            event.redirectURI = action.redirect.getAttribute('uri')
        self.deleteReceived(event)


    def _onEvent_purge(self, sender, recipient, action, headers):
        nodeIdentifier = action["node"]
        event = PurgeEvent(sender, recipient, nodeIdentifier, headers)
        self.purgeReceived(event)


    def itemsReceived(self, event):
        pass


    def deleteReceived(self, event):
        pass


    def purgeReceived(self, event):
        pass


    def createNode(self, service, nodeIdentifier=None, options=None,
                         sender=None):
        """
        Create a publish subscribe node.

        @param service: The publish subscribe service to create the node at.
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}
        @param nodeIdentifier: Optional suggestion for the id of the node.
        @type nodeIdentifier: L{unicode}
        @param options: Optional node configuration options.
        @type options: L{dict}
        """
        request = PubSubRequest('create')
        request.recipient = service
        request.nodeIdentifier = nodeIdentifier
        request.sender = sender

        if options:
            form = data_form.Form(formType='submit',
                                  formNamespace=NS_PUBSUB_NODE_CONFIG)
            form.makeFields(options)
            request.options = form

        def cb(iq):
            try:
                new_node = iq.pubsub.create["node"]
            except AttributeError:
                # the suggested node identifier was accepted
                new_node = nodeIdentifier
            return new_node

        d = request.send(self.xmlstream)
        d.addCallback(cb)
        return d


    def deleteNode(self, service, nodeIdentifier, sender=None):
        """
        Delete a publish subscribe node.

        @param service: The publish subscribe service to delete the node from.
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}
        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: L{unicode}
        """
        request = PubSubRequest('delete')
        request.recipient = service
        request.nodeIdentifier = nodeIdentifier
        request.sender = sender
        return request.send(self.xmlstream)


    def subscribe(self, service, nodeIdentifier, subscriber,
                        options=None, sender=None):
        """
        Subscribe to a publish subscribe node.

        @param service: The publish subscribe service that keeps the node.
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: L{unicode}

        @param subscriber: The entity to subscribe to the node. This entity
            will get notifications of new published items.
        @type subscriber: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param options: Subscription options.
        @type options: L{dict}

        @return: Deferred that fires with L{Subscription} or errbacks with
            L{SubscriptionPending} or L{SubscriptionUnconfigured}.
        @rtype: L{defer.Deferred}
        """
        request = PubSubRequest('subscribe')
        request.recipient = service
        request.nodeIdentifier = nodeIdentifier
        request.subscriber = subscriber
        request.sender = sender

        if options:
            form = data_form.Form(formType='submit',
                                  formNamespace=NS_PUBSUB_SUBSCRIBE_OPTIONS)
            form.makeFields(options)
            request.options = form

        def cb(iq):
            subscription = Subscription.fromElement(iq.pubsub.subscription)

            if subscription.state == 'pending':
                raise SubscriptionPending()
            elif subscription.state == 'unconfigured':
                raise SubscriptionUnconfigured()
            else:
                # we assume subscription == 'subscribed'
                # any other value would be invalid, but that should have
                # yielded a stanza error.
                return subscription

        d = request.send(self.xmlstream)
        d.addCallback(cb)
        return d


    def unsubscribe(self, service, nodeIdentifier, subscriber,
                          subscriptionIdentifier=None, sender=None):
        """
        Unsubscribe from a publish subscribe node.

        @param service: The publish subscribe service that keeps the node.
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: L{unicode}

        @param subscriber: The entity to unsubscribe from the node.
        @type subscriber: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param subscriptionIdentifier: Optional subscription identifier.
        @type subscriptionIdentifier: L{unicode}
        """
        request = PubSubRequest('unsubscribe')
        request.recipient = service
        request.nodeIdentifier = nodeIdentifier
        request.subscriber = subscriber
        request.subscriptionIdentifier = subscriptionIdentifier
        request.sender = sender
        return request.send(self.xmlstream)


    def publish(self, service, nodeIdentifier, items=None, sender=None):
        """
        Publish to a publish subscribe node.

        @param service: The publish subscribe service that keeps the node.
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}
        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: L{unicode}
        @param items: Optional list of L{Item}s to publish.
        @type items: L{list}
        """
        request = PubSubRequest('publish')
        request.recipient = service
        request.nodeIdentifier = nodeIdentifier
        request.items = items
        request.sender = sender
        return request.send(self.xmlstream)


    def items(self, service, nodeIdentifier, maxItems=None,
              subscriptionIdentifier=None, sender=None, itemIdentifiers=None):
        """
        Retrieve previously published items from a publish subscribe node.

        @param service: The publish subscribe service that keeps the node.
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: L{unicode}

        @param maxItems: Optional limit on the number of retrieved items.
        @type maxItems: L{int}

        @param subscriptionIdentifier: Optional subscription identifier. In
            case the node has been subscribed to multiple times, this narrows
            the results to the specific subscription.
        @type subscriptionIdentifier: L{unicode}

        @param itemIdentifiers: Identifiers of the items to be retrieved.
        @type itemIdentifiers: L{set} of L{unicode}
        """
        request = PubSubRequest('items')
        request.recipient = service
        request.nodeIdentifier = nodeIdentifier
        if maxItems:
            request.maxItems = str(int(maxItems))
        request.subscriptionIdentifier = subscriptionIdentifier
        request.sender = sender
        request.itemIdentifiers = itemIdentifiers

        def cb(iq):
            items = []
            for element in iq.pubsub.items.elements():
                if element.uri == NS_PUBSUB and element.name == 'item':
                    items.append(element)
            return items

        d = request.send(self.xmlstream)
        d.addCallback(cb)
        return d


    def getOptions(self, service, nodeIdentifier, subscriber,
                         subscriptionIdentifier=None, sender=None):
        """
        Get subscription options.

        @param service: The publish subscribe service that keeps the node.
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: L{unicode}

        @param subscriber: The entity subscribed to the node.
        @type subscriber: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param subscriptionIdentifier: Optional subscription identifier.
        @type subscriptionIdentifier: L{unicode}

        @rtype: L{data_form.Form}
        """
        request = PubSubRequest('optionsGet')
        request.recipient = service
        request.nodeIdentifier = nodeIdentifier
        request.subscriber = subscriber
        request.subscriptionIdentifier = subscriptionIdentifier
        request.sender = sender

        def cb(iq):
            form = data_form.findForm(iq.pubsub.options,
                                      NS_PUBSUB_SUBSCRIBE_OPTIONS)
            form.typeCheck()
            return form

        d = request.send(self.xmlstream)
        d.addCallback(cb)
        return d


    def setOptions(self, service, nodeIdentifier, subscriber,
                         options, subscriptionIdentifier=None, sender=None):
        """
        Set subscription options.

        @param service: The publish subscribe service that keeps the node.
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: L{unicode}

        @param subscriber: The entity subscribed to the node.
        @type subscriber: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param options: Subscription options.
        @type options: L{dict}.

        @param subscriptionIdentifier: Optional subscription identifier.
        @type subscriptionIdentifier: L{unicode}
        """
        request = PubSubRequest('optionsSet')
        request.recipient = service
        request.nodeIdentifier = nodeIdentifier
        request.subscriber = subscriber
        request.subscriptionIdentifier = subscriptionIdentifier
        request.sender = sender

        form = data_form.Form(formType='submit',
                              formNamespace=NS_PUBSUB_SUBSCRIBE_OPTIONS)
        form.makeFields(options)
        request.options = form

        d = request.send(self.xmlstream)
        return d



@implementer(IPubSubService, disco.IDisco)
class PubSubService(XMPPHandler, IQHandlerMixin):
    """
    Protocol implementation for a XMPP Publish Subscribe Service.

    The word Service here is used as taken from the Publish Subscribe
    specification. It is the party responsible for keeping nodes and their
    subscriptions, and sending out notifications.

    Methods from the L{IPubSubService} interface that are called as a result
    of an XMPP request may raise exceptions. Alternatively the deferred
    returned by these methods may have their errback called. These are handled
    as follows:

     - If the exception is an instance of L{error.StanzaError}, an error
       response iq is returned.
     - Any other exception is reported using L{log.msg}. An error response
       with the condition C{internal-server-error} is returned.

    The default implementation of said methods raises an L{Unsupported}
    exception and are meant to be overridden.

    @ivar discoIdentity: Service discovery identity as a dictionary with
                         keys C{'category'}, C{'type'} and C{'name'}.
    @ivar pubSubFeatures: List of supported publish-subscribe features for
                          service discovery, as L{str}.
    @type pubSubFeatures: L{list} or L{None}
    """

    iqHandlers = {
            '/*': '_onPubSubRequest',
            }

    _legacyHandlers = {
        'publish': ('publish', ['sender', 'recipient',
                                'nodeIdentifier', 'items']),
        'subscribe': ('subscribe', ['sender', 'recipient',
                                    'nodeIdentifier', 'subscriber']),
        'unsubscribe': ('unsubscribe', ['sender', 'recipient',
                                        'nodeIdentifier', 'subscriber']),
        'subscriptions': ('subscriptions', ['sender', 'recipient']),
        'affiliations': ('affiliations', ['sender', 'recipient']),
        'create': ('create', ['sender', 'recipient', 'nodeIdentifier']),
        'getConfigurationOptions': ('getConfigurationOptions', []),
        'default': ('getDefaultConfiguration',
                    ['sender', 'recipient', 'nodeType']),
        'configureGet': ('getConfiguration', ['sender', 'recipient',
                                              'nodeIdentifier']),
        'configureSet': ('setConfiguration', ['sender', 'recipient',
                                              'nodeIdentifier', 'options']),
        'items': ('items', ['sender', 'recipient', 'nodeIdentifier',
                            'maxItems', 'itemIdentifiers']),
        'retract': ('retract', ['sender', 'recipient', 'nodeIdentifier',
                                'itemIdentifiers']),
        'purge': ('purge', ['sender', 'recipient', 'nodeIdentifier']),
        'delete': ('delete', ['sender', 'recipient', 'nodeIdentifier']),
    }

    hideNodes = False

    def __init__(self, resource=None):
        self.resource = resource
        self.discoIdentity = {'category': 'pubsub',
                              'type': 'service',
                              'name': 'Generic Publish-Subscribe Service'}

        self.pubSubFeatures = []


    def connectionMade(self):
        self.xmlstream.addObserver(PUBSUB_REQUEST, self.handleRequest)


    def getDiscoInfo(self, requestor, target, nodeIdentifier=''):
        def toInfo(nodeInfo):
            if not nodeInfo:
                return

            (nodeType, metaData) = nodeInfo['type'], nodeInfo['meta-data']
            info.append(disco.DiscoIdentity('pubsub', nodeType))
            if metaData:
                form = data_form.Form(formType="result",
                                      formNamespace=NS_PUBSUB_META_DATA)
                form.addField(
                        data_form.Field(
                            var='pubsub#node_type',
                            value=nodeType,
                            label='The type of node (collection or leaf)'
                        )
                )

                for metaDatum in metaData:
                    form.addField(data_form.Field.fromDict(metaDatum))

                info.append(form)

            return

        info = []

        request = PubSubRequest('discoInfo')

        if self.resource is not None:
            resource = self.resource.locateResource(request)
            identity = resource.discoIdentity
            features = resource.features
            getInfo = resource.getInfo
        else:
            category = self.discoIdentity['category']
            idType = self.discoIdentity['type']
            name = self.discoIdentity['name']
            identity = disco.DiscoIdentity(category, idType, name)
            features = self.pubSubFeatures
            getInfo = self.getNodeInfo

        if not nodeIdentifier:
            info.append(identity)
            info.append(disco.DiscoFeature(disco.NS_DISCO_ITEMS))
            info.extend([disco.DiscoFeature("%s#%s" % (NS_PUBSUB, feature))
                         for feature in features])

        d = defer.maybeDeferred(getInfo, requestor, target, nodeIdentifier or '')
        d.addCallback(toInfo)
        d.addErrback(log.err)
        d.addCallback(lambda _: info)
        return d


    def getDiscoItems(self, requestor, target, nodeIdentifier=''):
        if self.hideNodes:
            d = defer.succeed([])
        elif self.resource is not None:
            request = PubSubRequest('discoInfo')
            resource = self.resource.locateResource(request)
            d = resource.getNodes(requestor, target, nodeIdentifier)
        elif nodeIdentifier:
            d = self.getNodes(requestor, target)
        else:
            d = defer.succeed([])

        d.addCallback(lambda nodes: [disco.DiscoItem(target, node)
                                     for node in nodes])
        return d


    def _onPubSubRequest(self, iq):
        request = PubSubRequest.fromElement(iq)

        if self.resource is not None:
            resource = self.resource.locateResource(request)
        else:
            resource = self

        # Preprocess the request, knowing the handling resource
        try:
            preProcessor = getattr(self, '_preProcess_%s' % request.verb)
        except AttributeError:
            pass
        else:
            request = preProcessor(resource, request)
            if request is None:
                return defer.succeed(None)

        # Process the request itself, 
        if resource is not self:
            try:
                handler = getattr(resource, request.verb)
            except AttributeError:
                text = "Request verb: %s" % request.verb
                return defer.fail(Unsupported('', text))

            d = handler(request)
        else:
            try:
                handlerName, argNames = self._legacyHandlers[request.verb]
            except KeyError:
                text = "Request verb: %s" % request.verb
                return defer.fail(Unsupported('', text))

            handler = getattr(self, handlerName)
            args = [getattr(request, arg) for arg in argNames]
            d = handler(*args)

        # If needed, translate the result into a response
        try:
            cb = getattr(self, '_toResponse_%s' % request.verb)
        except AttributeError:
            pass
        else:
            d.addCallback(cb, resource, request)

        return d


    def _toResponse_subscribe(self, result, resource, request):
        response = domish.Element((NS_PUBSUB, "pubsub"))
        response.addChild(result.toElement(NS_PUBSUB))
        return response


    def _toResponse_subscriptions(self, result, resource, request):
        response = domish.Element((NS_PUBSUB, 'pubsub'))
        subscriptions = response.addElement('subscriptions')
        for subscription in result:
            subscriptions.addChild(subscription.toElement(NS_PUBSUB))
        return response


    def _toResponse_affiliations(self, result, resource, request):
        response = domish.Element((NS_PUBSUB, 'pubsub'))
        affiliations = response.addElement('affiliations')

        for nodeIdentifier, affiliation in result:
            item = affiliations.addElement('affiliation')
            item['node'] = nodeIdentifier
            item['affiliation'] = affiliation

        return response


    def _toResponse_create(self, result, resource, request):
        if not request.nodeIdentifier or request.nodeIdentifier != result:
            response = domish.Element((NS_PUBSUB, 'pubsub'))
            create = response.addElement('create')
            create['node'] = result
            return response
        else:
            return None


    def _formFromConfiguration(self, resource, values):
        fieldDefs = resource.getConfigurationOptions()
        form = data_form.Form(formType="form",
                              formNamespace=NS_PUBSUB_NODE_CONFIG)
        form.makeFields(values, fieldDefs)
        return form


    def _checkConfiguration(self, resource, form):
        fieldDefs = resource.getConfigurationOptions()
        form.typeCheck(fieldDefs, filterUnknown=True)


    def _preProcess_create(self, resource, request):
        if request.options:
            self._checkConfiguration(resource, request.options)
        return request


    def _preProcess_default(self, resource, request):
        if request.nodeType not in ('leaf', 'collection'):
            raise error.StanzaError('not-acceptable')
        else:
            return request


    def _toResponse_default(self, options, resource, request):
        response = domish.Element((NS_PUBSUB_OWNER, "pubsub"))
        default = response.addElement("default")
        form = self._formFromConfiguration(resource, options)
        default.addChild(form.toElement())
        return response


    def _toResponse_configureGet(self, options, resource, request):
        response = domish.Element((NS_PUBSUB_OWNER, "pubsub"))
        configure = response.addElement("configure")
        form = self._formFromConfiguration(resource, options)
        configure.addChild(form.toElement())

        if request.nodeIdentifier:
            configure["node"] = request.nodeIdentifier

        return response


    def _preProcess_configureSet(self, resource, request):
        if request.options.formType == 'cancel':
            return None
        else:
            self._checkConfiguration(resource, request.options)
            return request


    def _toResponse_items(self, result, resource, request):
        response = domish.Element((NS_PUBSUB, 'pubsub'))
        items = response.addElement('items')
        items["node"] = request.nodeIdentifier

        for item in result:
            item.uri = NS_PUBSUB
            items.addChild(item)

        return response


    def _createNotification(self, eventType, service, nodeIdentifier,
                                  subscriber, subscriptions=None):
        headers = []

        if subscriptions:
            for subscription in subscriptions:
                if nodeIdentifier != subscription.nodeIdentifier:
                    headers.append(('Collection', subscription.nodeIdentifier))

        message = domish.Element((None, "message"))
        message["from"] = service.full()
        message["to"] = subscriber.full()
        event = message.addElement((NS_PUBSUB_EVENT, "event"))

        element = event.addElement(eventType)
        element["node"] = nodeIdentifier

        if headers:
            message.addChild(shim.Headers(headers))

        return message


    def _toResponse_affiliationsGet(self, result, resource, request):
        response = domish.Element((NS_PUBSUB_OWNER, 'pubsub'))
        affiliations = response.addElement('affiliations')

        if request.nodeIdentifier:
            affiliations['node'] = request.nodeIdentifier

        for entity, affiliation in iteritems(result):
            item = affiliations.addElement('affiliation')
            item['jid'] = entity.full()
            item['affiliation'] = affiliation

        return response


    # public methods

    def notifyPublish(self, service, nodeIdentifier, notifications):
        for subscriber, subscriptions, items in notifications:
            message = self._createNotification('items', service,
                                               nodeIdentifier, subscriber,
                                               subscriptions)
            for item in items:
                item.uri = NS_PUBSUB_EVENT
                message.event.items.addChild(item)
            self.send(message)


    def notifyDelete(self, service, nodeIdentifier, subscribers,
                           redirectURI=None):
        for subscriber in subscribers:
            message = self._createNotification('delete', service,
                                               nodeIdentifier,
                                               subscriber)
            if redirectURI:
                redirect = message.event.delete.addElement('redirect')
                redirect['uri'] = redirectURI
            self.send(message)


    def getNodeInfo(self, requestor, service, nodeIdentifier):
        return None


    def getNodes(self, requestor, service):
        return []


    def publish(self, requestor, service, nodeIdentifier, items):
        raise Unsupported('publish')


    def subscribe(self, requestor, service, nodeIdentifier, subscriber):
        raise Unsupported('subscribe')


    def unsubscribe(self, requestor, service, nodeIdentifier, subscriber):
        raise Unsupported('subscribe')


    def subscriptions(self, requestor, service):
        raise Unsupported('retrieve-subscriptions')


    def affiliations(self, requestor, service):
        raise Unsupported('retrieve-affiliations')


    def create(self, requestor, service, nodeIdentifier):
        raise Unsupported('create-nodes')


    def getConfigurationOptions(self):
        return {}


    def getDefaultConfiguration(self, requestor, service, nodeType):
        raise Unsupported('retrieve-default')


    def getConfiguration(self, requestor, service, nodeIdentifier):
        raise Unsupported('config-node')


    def setConfiguration(self, requestor, service, nodeIdentifier, options):
        raise Unsupported('config-node')


    def items(self, requestor, service, nodeIdentifier, maxItems,
                    itemIdentifiers):
        raise Unsupported('retrieve-items')


    def retract(self, requestor, service, nodeIdentifier, itemIdentifiers):
        raise Unsupported('retract-items')


    def purge(self, requestor, service, nodeIdentifier):
        raise Unsupported('purge-nodes')


    def delete(self, requestor, service, nodeIdentifier):
        raise Unsupported('delete-nodes')



@implementer(IPubSubResource)
class PubSubResource(object):

    features = []
    discoIdentity = disco.DiscoIdentity('pubsub',
                                        'service',
                                        'Publish-Subscribe Service')


    def locateResource(self, request):
        return self


    def getInfo(self, requestor, service, nodeIdentifier):
        return defer.succeed(None)


    def getNodes(self, requestor, service, nodeIdentifier):
        return defer.succeed([])


    def getConfigurationOptions(self):
        return {}


    def publish(self, request):
        return defer.fail(Unsupported('publish'))


    def subscribe(self, request):
        return defer.fail(Unsupported('subscribe'))


    def unsubscribe(self, request):
        return defer.fail(Unsupported('subscribe'))


    def subscriptions(self, request):
        return defer.fail(Unsupported('retrieve-subscriptions'))


    def affiliations(self, request):
        return defer.fail(Unsupported('retrieve-affiliations'))


    def create(self, request):
        return defer.fail(Unsupported('create-nodes'))


    def default(self, request):
        return defer.fail(Unsupported('retrieve-default'))


    def configureGet(self, request):
        return defer.fail(Unsupported('config-node'))


    def configureSet(self, request):
        return defer.fail(Unsupported('config-node'))


    def items(self, request):
        return defer.fail(Unsupported('retrieve-items'))


    def retract(self, request):
        return defer.fail(Unsupported('retract-items'))


    def purge(self, request):
        return defer.fail(Unsupported('purge-nodes'))


    def delete(self, request):
        return defer.fail(Unsupported('delete-nodes'))


    def affiliationsGet(self, request):
        return defer.fail(Unsupported('modify-affiliations'))


    def affiliationsSet(self, request):
        return defer.fail(Unsupported('modify-affiliations'))


    def subscriptionsGet(self, request):
        return defer.fail(Unsupported('manage-subscriptions'))


    def subscriptionsSet(self, request):
        return defer.fail(Unsupported('manage-subscriptions'))
