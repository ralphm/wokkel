# -*- test-case-name: wokkel.test.test_pubsub -*-
#
# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
XMPP publish-subscribe protocol.

This protocol is specified in
U{XEP-0060<http://www.xmpp.org/extensions/xep-0060.html>}.
"""

from zope.interface import implements

from twisted.internet import defer
from twisted.words.protocols.jabber import jid, error, xmlstream
from twisted.words.xish import domish

from wokkel import disco, data_form, shim
from wokkel.subprotocols import IQHandlerMixin, XMPPHandler
from wokkel.iwokkel import IPubSubClient, IPubSubService

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

# In publish-subscribe namespace XPath query selector.
IN_NS_PUBSUB = '[@xmlns="' + NS_PUBSUB + '"]'
IN_NS_PUBSUB_OWNER = '[@xmlns="' + NS_PUBSUB_OWNER + '"]'

# Publish-subscribe XPath queries
PUBSUB_ELEMENT = '/pubsub' + IN_NS_PUBSUB
PUBSUB_OWNER_ELEMENT = '/pubsub' + IN_NS_PUBSUB_OWNER
PUBSUB_GET = IQ_GET + PUBSUB_ELEMENT
PUBSUB_SET = IQ_SET + PUBSUB_ELEMENT
PUBSUB_OWNER_GET = IQ_GET + PUBSUB_OWNER_ELEMENT
PUBSUB_OWNER_SET = IQ_SET + PUBSUB_OWNER_ELEMENT

# Publish-subscribe command XPath queries
PUBSUB_PUBLISH = PUBSUB_SET + '/publish' + IN_NS_PUBSUB
PUBSUB_CREATE = PUBSUB_SET + '/create' + IN_NS_PUBSUB
PUBSUB_SUBSCRIBE = PUBSUB_SET + '/subscribe' + IN_NS_PUBSUB
PUBSUB_UNSUBSCRIBE = PUBSUB_SET + '/unsubscribe' + IN_NS_PUBSUB
PUBSUB_OPTIONS_GET = PUBSUB_GET + '/options' + IN_NS_PUBSUB
PUBSUB_OPTIONS_SET = PUBSUB_SET + '/options' + IN_NS_PUBSUB
PUBSUB_DEFAULT = PUBSUB_OWNER_GET + '/default' + IN_NS_PUBSUB_OWNER
PUBSUB_CONFIGURE_GET = PUBSUB_OWNER_GET + '/configure' + IN_NS_PUBSUB_OWNER
PUBSUB_CONFIGURE_SET = PUBSUB_OWNER_SET + '/configure' + IN_NS_PUBSUB_OWNER
PUBSUB_SUBSCRIPTIONS = PUBSUB_GET + '/subscriptions' + IN_NS_PUBSUB
PUBSUB_AFFILIATIONS = PUBSUB_GET + '/affiliations' + IN_NS_PUBSUB
PUBSUB_AFFILIATIONS_GET = PUBSUB_OWNER_GET + '/affiliations' + \
                          IN_NS_PUBSUB_OWNER
PUBSUB_AFFILIATIONS_SET = PUBSUB_OWNER_SET + '/affiliations' + \
                          IN_NS_PUBSUB_OWNER
PUBSUB_SUBSCRIPTIONS_GET = PUBSUB_OWNER_GET + '/subscriptions' + \
                          IN_NS_PUBSUB_OWNER
PUBSUB_SUBSCRIPTIONS_SET = PUBSUB_OWNER_SET + '/subscriptions' + \
                          IN_NS_PUBSUB_OWNER
PUBSUB_ITEMS = PUBSUB_GET + '/items' + IN_NS_PUBSUB
PUBSUB_RETRACT = PUBSUB_SET + '/retract' + IN_NS_PUBSUB
PUBSUB_PURGE = PUBSUB_OWNER_SET + '/purge' + IN_NS_PUBSUB_OWNER
PUBSUB_DELETE = PUBSUB_OWNER_SET + '/delete' + IN_NS_PUBSUB_OWNER

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



class BadRequest(PubSubError):
    """
    Bad request stanza error.
    """
    def __init__(self, pubsubCondition=None, text=None):
        PubSubError.__init__(self, 'bad-request', pubsubCondition, text)



class Unsupported(PubSubError):
    def __init__(self, feature, text=None):
        PubSubError.__init__(self, 'feature-not-implemented',
                                   'unsupported',
                                   feature,
                                   text)



class Subscription(object):
    """
    A subscription to a node.

    @ivar nodeIdentifier: The identifier of the node subscribed to.
                          The root node is denoted by C{None}.
    @ivar subscriber: The subscribing entity.
    @ivar state: The subscription state. One of C{'subscribed'}, C{'pending'},
                 C{'unconfigured'}.
    @ivar options: Optional list of subscription options.
    @type options: C{dict}.
    """

    def __init__(self, nodeIdentifier, subscriber, state, options=None):
        self.nodeIdentifier = nodeIdentifier
        self.subscriber = subscriber
        self.state = state
        self.options = options or {}



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

        domish.Element.__init__(self, (NS_PUBSUB, 'item'))
        if id is not None:
            self['id'] = id
        if payload is not None:
            if isinstance(payload, basestring):
                self.addRawXml(payload)
            else:
                self.addChild(payload)



class _PubSubRequest(xmlstream.IQ):
    """
    Publish subscribe request.

    @ivar verb: Request verb
    @type verb: C{str}
    @ivar namespace: Request namespace.
    @type namespace: C{str}
    @ivar method: Type attribute of the IQ request. Either C{'set'} or C{'get'}
    @type method: C{str}
    @ivar command: Command element of the request. This is the direct child of
                   the C{pubsub} element in the C{namespace} with the name
                   C{verb}.
    """

    def __init__(self, xs, verb, namespace=NS_PUBSUB, method='set'):
        xmlstream.IQ.__init__(self, xs, method)
        self.addElement((namespace, 'pubsub'))

        self.command = self.pubsub.addElement(verb)


    def send(self, to):
        """
        Send out request.

        Extends L{xmlstream.IQ.send} by requiring the C{to} parameter to be
        a L{JID} instance.

        @param to: Entity to send the request to.
        @type to: L{JID}
        """
        destination = to.full()
        return xmlstream.IQ.send(self, destination)



class PubSubEvent(object):
    """
    A publish subscribe event.

    @param sender: The entity from which the notification was received.
    @type sender: L{jid.JID}
    @param recipient: The entity to which the notification was sent.
    @type recipient: L{wokkel.pubsub.ItemsEvent}
    @param nodeIdentifier: Identifier of the node the event pertains to.
    @type nodeIdentifier: C{unicode}
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
    @type items: C{list} of L{domish.Element}
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



class PubSubClient(XMPPHandler):
    """
    Publish subscribe client protocol.
    """

    implements(IPubSubClient)

    def connectionInitialized(self):
        self.xmlstream.addObserver('/message/event[@xmlns="%s"]' %
                                   NS_PUBSUB_EVENT, self._onEvent)


    def _onEvent(self, message):
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


    def createNode(self, service, nodeIdentifier=None):
        """
        Create a publish subscribe node.

        @param service: The publish subscribe service to create the node at.
        @type service: L{JID}
        @param nodeIdentifier: Optional suggestion for the id of the node.
        @type nodeIdentifier: C{unicode}
        """


        request = _PubSubRequest(self.xmlstream, 'create')
        if nodeIdentifier:
            request.command['node'] = nodeIdentifier

        def cb(iq):
            try:
                new_node = iq.pubsub.create["node"]
            except AttributeError:
                # the suggested node identifier was accepted
                new_node = nodeIdentifier
            return new_node

        return request.send(service).addCallback(cb)


    def deleteNode(self, service, nodeIdentifier):
        """
        Delete a publish subscribe node.

        @param service: The publish subscribe service to delete the node from.
        @type service: L{JID}
        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: C{unicode}
        """
        request = _PubSubRequest(self.xmlstream, 'delete', NS_PUBSUB_OWNER)
        request.command['node'] = nodeIdentifier
        return request.send(service)


    def subscribe(self, service, nodeIdentifier, subscriber):
        """
        Subscribe to a publish subscribe node.

        @param service: The publish subscribe service that keeps the node.
        @type service: L{JID}
        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: C{unicode}
        @param subscriber: The entity to subscribe to the node. This entity
                           will get notifications of new published items.
        @type subscriber: L{JID}
        """
        request = _PubSubRequest(self.xmlstream, 'subscribe')
        if nodeIdentifier:
            request.command['node'] = nodeIdentifier
        request.command['jid'] = subscriber.full()

        def cb(iq):
            subscription = iq.pubsub.subscription["subscription"]

            if subscription == 'pending':
                raise SubscriptionPending
            elif subscription == 'unconfigured':
                raise SubscriptionUnconfigured
            else:
                # we assume subscription == 'subscribed'
                # any other value would be invalid, but that should have
                # yielded a stanza error.
                return None

        return request.send(service).addCallback(cb)


    def unsubscribe(self, service, nodeIdentifier, subscriber):
        """
        Unsubscribe from a publish subscribe node.

        @param service: The publish subscribe service that keeps the node.
        @type service: L{JID}
        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: C{unicode}
        @param subscriber: The entity to unsubscribe from the node.
        @type subscriber: L{JID}
        """
        request = _PubSubRequest(self.xmlstream, 'unsubscribe')
        if nodeIdentifier:
            request.command['node'] = nodeIdentifier
        request.command['jid'] = subscriber.full()
        return request.send(service)


    def publish(self, service, nodeIdentifier, items=None):
        """
        Publish to a publish subscribe node.

        @param service: The publish subscribe service that keeps the node.
        @type service: L{JID}
        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: C{unicode}
        @param items: Optional list of L{Item}s to publish.
        @type items: C{list}
        """
        request = _PubSubRequest(self.xmlstream, 'publish')
        request.command['node'] = nodeIdentifier
        if items:
            for item in items:
                request.command.addChild(item)

        return request.send(service)


    def items(self, service, nodeIdentifier, maxItems=None):
        """
        Retrieve previously published items from a publish subscribe node.

        @param service: The publish subscribe service that keeps the node.
        @type service: L{JID}
        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: C{unicode}
        @param maxItems: Optional limit on the number of retrieved items.
        @type maxItems: C{int}
        """
        request = _PubSubRequest(self.xmlstream, 'items', method='get')
        if nodeIdentifier:
            request.command['node'] = nodeIdentifier
        if maxItems:
            request.command["max_items"] = str(int(maxItems))

        def cb(iq):
            items = []
            for element in iq.pubsub.items.elements():
                if element.uri == NS_PUBSUB and element.name == 'item':
                    items.append(element)
            return items

        return request.send(service).addCallback(cb)



class PubSubService(XMPPHandler, IQHandlerMixin):
    """
    Protocol implementation for a XMPP Publish Subscribe Service.

    The word Service here is used as taken from the Publish Subscribe
    specification. It is the party responsible for keeping nodes and their
    subscriptions, and sending out notifications.

    Methods from the L{IPubSubService} interface that are called as
    a result of an XMPP request may raise exceptions. Alternatively the
    deferred returned by these methods may have their errback called. These are
    handled as follows:

     - If the exception is an instance of L{error.StanzaError}, an error
       response iq is returned.
     - Any other exception is reported using L{log.msg}. An error response
       with the condition C{internal-server-error} is returned.

    The default implementation of said methods raises an L{Unsupported}
    exception and are meant to be overridden.

    @ivar discoIdentity: Service discovery identity as a dictionary with
                         keys C{'category'}, C{'type'} and C{'name'}.
    @ivar pubSubFeatures: List of supported publish-subscribe features for
                          service discovery, as C{str}.
    @type pubSubFeatures: C{list} or C{None}
    """

    implements(IPubSubService)

    iqHandlers = {
            PUBSUB_PUBLISH: '_onPublish',
            PUBSUB_CREATE: '_onCreate',
            PUBSUB_SUBSCRIBE: '_onSubscribe',
            PUBSUB_OPTIONS_GET: '_onOptionsGet',
            PUBSUB_OPTIONS_SET: '_onOptionsSet',
            PUBSUB_AFFILIATIONS: '_onAffiliations',
            PUBSUB_ITEMS: '_onItems',
            PUBSUB_RETRACT: '_onRetract',
            PUBSUB_SUBSCRIPTIONS: '_onSubscriptions',
            PUBSUB_UNSUBSCRIBE: '_onUnsubscribe',

            PUBSUB_AFFILIATIONS_GET: '_onAffiliationsGet',
            PUBSUB_AFFILIATIONS_SET: '_onAffiliationsSet',
            PUBSUB_CONFIGURE_GET: '_onConfigureGet',
            PUBSUB_CONFIGURE_SET: '_onConfigureSet',
            PUBSUB_DEFAULT: '_onDefault',
            PUBSUB_PURGE: '_onPurge',
            PUBSUB_DELETE: '_onDelete',
            PUBSUB_SUBSCRIPTIONS_GET: '_onSubscriptionsGet',
            PUBSUB_SUBSCRIPTIONS_SET: '_onSubscriptionsSet',

            }


    def __init__(self):
        self.discoIdentity = {'category': 'pubsub',
                              'type': 'generic',
                              'name': 'Generic Publish-Subscribe Service'}

        self.pubSubFeatures = []


    def connectionMade(self):
        self.xmlstream.addObserver(PUBSUB_GET, self.handleRequest)
        self.xmlstream.addObserver(PUBSUB_SET, self.handleRequest)
        self.xmlstream.addObserver(PUBSUB_OWNER_GET, self.handleRequest)
        self.xmlstream.addObserver(PUBSUB_OWNER_SET, self.handleRequest)


    def getDiscoInfo(self, requestor, target, nodeIdentifier):
        info = []

        if not nodeIdentifier:
            category, idType, name = self.discoIdentity
            info.append(disco.DiscoIdentity(category, idType, name))

            info.append(disco.DiscoFeature(disco.NS_DISCO_ITEMS))
            info.extend([disco.DiscoFeature("%s#%s" % (NS_PUBSUB, feature))
                         for feature in self.pubSubFeatures])

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

        d = self.getNodeInfo(requestor, target, nodeIdentifier or '')
        d.addCallback(toInfo)
        d.addBoth(lambda result: info)
        return d


    def getDiscoItems(self, requestor, target, nodeIdentifier):
        if nodeIdentifier or self.hideNodes:
            return defer.succeed([])

        d = self.getNodes(requestor, target)
        d.addCallback(lambda nodes: [disco.DiscoItem(target, node)
                                     for node in nodes])
        return d


    def _findForm(self, element, formNamespace):
        if not element:
            return None

        form = None
        for child in element.elements():
            try:
                form = data_form.Form.fromElement(child)
            except data_form.Error:
                continue

            if form.formNamespace != NS_PUBSUB_NODE_CONFIG:
                continue

        return form


    def _getParameter_node(self, commandElement):
        try:
            return commandElement["node"]
        except KeyError:
            raise BadRequest('nodeid-required')


    def _getParameter_nodeOrEmpty(self, commandElement):
        return commandElement.getAttribute("node", '')


    def _getParameter_jid(self, commandElement):
        try:
            return jid.internJID(commandElement["jid"])
        except KeyError:
            raise BadRequest('jid-required')


    def _getParameter_max_items(self, commandElement):
        value = commandElement.getAttribute('max_items')

        if value:
            try:
                return int(value)
            except ValueError:
                raise BadRequest(text="Field max_items requires a positive " +
                                      "integer value")
        else:
            return None


    def _getParameters(self, iq, *names):
        requestor = jid.internJID(iq["from"]).userhostJID()
        service = jid.internJID(iq["to"])

        params = [requestor, service]

        if names:
            command = names[0]
            commandElement = getattr(iq.pubsub, command)
            if not commandElement:
                raise Exception("Could not find command element %r" % command)

        for name in names[1:]:
            try:
                getter = getattr(self, '_getParameter_' + name)
            except KeyError:
                raise Exception("No parameter getter for this name")

            params.append(getter(commandElement))

        return params


    def _onPublish(self, iq):
        requestor, service, nodeIdentifier = self._getParameters(
                iq, 'publish', 'node')

        items = []
        for element in iq.pubsub.publish.elements():
            if element.uri == NS_PUBSUB and element.name == 'item':
                items.append(element)

        return self.publish(requestor, service, nodeIdentifier, items)


    def _onSubscribe(self, iq):
        requestor, service, nodeIdentifier, subscriber = self._getParameters(
                iq, 'subscribe', 'nodeOrEmpty', 'jid')

        def toResponse(result):
            response = domish.Element((NS_PUBSUB, "pubsub"))
            subscription = response.addElement("subscription")
            if result.nodeIdentifier:
                subscription["node"] = result.nodeIdentifier
            subscription["jid"] = result.subscriber.full()
            subscription["subscription"] = result.state
            return response

        d = self.subscribe(requestor, service, nodeIdentifier, subscriber)
        d.addCallback(toResponse)
        return d


    def _onUnsubscribe(self, iq):
        requestor, service, nodeIdentifier, subscriber = self._getParameters(
                iq, 'unsubscribe', 'nodeOrEmpty', 'jid')

        return self.unsubscribe(requestor, service, nodeIdentifier, subscriber)


    def _onOptionsGet(self, iq):
        raise Unsupported('subscription-options')


    def _onOptionsSet(self, iq):
        raise Unsupported('subscription-options')


    def _onSubscriptions(self, iq):
        requestor, service = self._getParameters(iq)

        def toResponse(result):
            response = domish.Element((NS_PUBSUB, 'pubsub'))
            subscriptions = response.addElement('subscriptions')
            for subscription in result:
                item = subscriptions.addElement('subscription')
                item['node'] = subscription.nodeIdentifier
                item['jid'] = subscription.subscriber.full()
                item['subscription'] = subscription.state
            return response

        d = self.subscriptions(requestor, service)
        d.addCallback(toResponse)
        return d


    def _onAffiliations(self, iq):
        requestor, service = self._getParameters(iq)

        def toResponse(result):
            response = domish.Element((NS_PUBSUB, 'pubsub'))
            affiliations = response.addElement('affiliations')

            for nodeIdentifier, affiliation in result:
                item = affiliations.addElement('affiliation')
                item['node'] = nodeIdentifier
                item['affiliation'] = affiliation

            return response

        d = self.affiliations(requestor, service)
        d.addCallback(toResponse)
        return d


    def _onCreate(self, iq):
        requestor, service = self._getParameters(iq)
        nodeIdentifier = iq.pubsub.create.getAttribute("node")

        def toResponse(result):
            if not nodeIdentifier or nodeIdentifier != result:
                response = domish.Element((NS_PUBSUB, 'pubsub'))
                create = response.addElement('create')
                create['node'] = result
                return response
            else:
                return None

        d = self.create(requestor, service, nodeIdentifier)
        d.addCallback(toResponse)
        return d


    def _makeFields(self, options, values):
        fields = []
        for name, value in values.iteritems():
            if name not in options:
                continue

            option = {'var': name}
            option.update(options[name])
            if isinstance(value, list):
                option['values'] = value
            else:
                option['value'] = value
            fields.append(data_form.Field.fromDict(option))
        return fields

    def _formFromConfiguration(self, values):
        options = self.getConfigurationOptions()
        fields = self._makeFields(options, values)
        form = data_form.Form(formType="form",
                              formNamespace=NS_PUBSUB_NODE_CONFIG,
                              fields=fields)

        return form

    def _checkConfiguration(self, values):
        options = self.getConfigurationOptions()
        processedValues = {}

        for key, value in values.iteritems():
            if key not in options:
                continue

            option = {'var': key}
            option.update(options[key])
            field = data_form.Field.fromDict(option)
            if isinstance(value, list):
                field.values = value
            else:
                field.value = value
            field.typeCheck()

            if isinstance(value, list):
                processedValues[key] = field.values
            else:
                processedValues[key] = field.value

        return processedValues


    def _onDefault(self, iq):
        requestor, service = self._getParameters(iq)

        def toResponse(options):
            response = domish.Element((NS_PUBSUB_OWNER, "pubsub"))
            default = response.addElement("default")
            default.addChild(self._formFromConfiguration(options).toElement())
            return response

        form = self._findForm(iq.pubsub.config, NS_PUBSUB_NODE_CONFIG)
        values = form and form.formType == 'result' and form.getValues() or {}
        nodeType = values.get('pubsub#node_type', 'leaf')

        if nodeType not in ('leaf', 'collections'):
            return defer.fail(error.StanzaError('not-acceptable'))

        d = self.getDefaultConfiguration(requestor, service, nodeType)
        d.addCallback(toResponse)
        return d


    def _onConfigureGet(self, iq):
        requestor, service, nodeIdentifier = self._getParameters(
                iq, 'configure', 'nodeOrEmpty')

        def toResponse(options):
            response = domish.Element((NS_PUBSUB_OWNER, "pubsub"))
            configure = response.addElement("configure")
            configure.addChild(self._formFromConfiguration(options).toElement())

            if nodeIdentifier:
                configure["node"] = nodeIdentifier

            return response

        d = self.getConfiguration(requestor, service, nodeIdentifier)
        d.addCallback(toResponse)
        return d


    def _onConfigureSet(self, iq):
        requestor, service, nodeIdentifier = self._getParameters(
                iq, 'configure', 'nodeOrEmpty')

        # Search configuration form with correct FORM_TYPE and process it

        form = self._findForm(iq.pubsub.configure, NS_PUBSUB_NODE_CONFIG)

        if form:
            if form.formType == 'submit':
                options = self._checkConfiguration(form.getValues())

                return self.setConfiguration(requestor, service,
                                             nodeIdentifier, options)
            elif form.formType == 'cancel':
                return None

        raise BadRequest()


    def _onItems(self, iq):
        requestor, service, nodeIdentifier, maxItems = self._getParameters(
                iq, 'items', 'nodeOrEmpty', 'max_items')

        itemIdentifiers = []
        for child in iq.pubsub.items.elements():
            if child.name == 'item' and child.uri == NS_PUBSUB:
                try:
                    itemIdentifiers.append(child["id"])
                except KeyError:
                    raise BadRequest()

        def toResponse(result):
            response = domish.Element((NS_PUBSUB, 'pubsub'))
            items = response.addElement('items')
            if nodeIdentifier:
                items["node"] = nodeIdentifier

            for item in result:
                items.addChild(item)

            return response

        d = self.items(requestor, service, nodeIdentifier, maxItems,
                       itemIdentifiers)
        d.addCallback(toResponse)
        return d


    def _onRetract(self, iq):
        requestor, service, nodeIdentifier = self._getParameters(
                iq, 'retract', 'node')

        itemIdentifiers = []
        for child in iq.pubsub.retract.elements():
            if child.uri == NS_PUBSUB and child.name == 'item':
                try:
                    itemIdentifiers.append(child["id"])
                except KeyError:
                    raise BadRequest()

        return self.retract(requestor, service, nodeIdentifier,
                            itemIdentifiers)


    def _onPurge(self, iq):
        requestor, service, nodeIdentifier = self._getParameters(
                iq, 'purge', 'node')
        return self.purge(requestor, service, nodeIdentifier)


    def _onDelete(self, iq):
        requestor, service, nodeIdentifier = self._getParameters(
                iq, 'delete', 'node')
        return self.delete(requestor, service, nodeIdentifier)


    def _onAffiliationsGet(self, iq):
        raise Unsupported('modify-affiliations')


    def _onAffiliationsSet(self, iq):
        raise Unsupported('modify-affiliations')


    def _onSubscriptionsGet(self, iq):
        raise Unsupported('manage-subscriptions')


    def _onSubscriptionsSet(self, iq):
        raise Unsupported('manage-subscriptions')

    # public methods

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

    def notifyPublish(self, service, nodeIdentifier, notifications):
        for subscriber, subscriptions, items in notifications:
            message = self._createNotification('items', service,
                                               nodeIdentifier, subscriber,
                                               subscriptions)
            message.event.items.children = items
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
