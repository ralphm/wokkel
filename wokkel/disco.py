# -*- test-case-name: wokkel.test.test_disco -*-
#
# Copyright (c) 2003-2009 Ralph Meijer
# See LICENSE for details.

"""
XMPP Service Discovery.

The XMPP service discovery protocol is documented in
U{XEP-0030<http://www.xmpp.org/extensions/xep-0030.html>}.
"""

from twisted.internet import defer
from twisted.words.protocols.jabber import error, jid, xmlstream
from twisted.words.xish import domish

from wokkel import data_form
from wokkel.iwokkel import IDisco
from wokkel.subprotocols import IQHandlerMixin, XMPPHandler

NS_DISCO = 'http://jabber.org/protocol/disco'
NS_DISCO_INFO = NS_DISCO + '#info'
NS_DISCO_ITEMS = NS_DISCO + '#items'

IQ_GET = '/iq[@type="get"]'
DISCO_INFO = IQ_GET + '/query[@xmlns="' + NS_DISCO_INFO + '"]'
DISCO_ITEMS = IQ_GET + '/query[@xmlns="' + NS_DISCO_ITEMS + '"]'

class DiscoFeature(unicode):
    """
    XMPP service discovery feature.

    This extends C{unicode} to convert to and from L{domish.Element}, but
    further behaves identically.
    """

    def toElement(self):
        """
        Render to a DOM representation.

        @rtype: L{domish.Element}.
        """
        element = domish.Element((NS_DISCO_INFO, 'feature'))
        element['var'] = unicode(self)
        return element


    @staticmethod
    def fromElement(element):
        """
        Parse a DOM representation into a L{DiscoFeature} instance.

        @param element: Element that represents the disco feature.
        @type element: L{domish.Element}.
        @rtype L{DiscoFeature}.
        """
        featureURI = element.getAttribute('var', u'')
        feature = DiscoFeature(featureURI)
        return feature



class DiscoIdentity(object):
    """
    XMPP service discovery identity.

    @ivar category: The identity category.
    @type category: C{unicode}
    @ivar type: The identity type.
    @type type: C{unicode}
    @ivar name: The optional natural language name for this entity.
    @type name: C{unicode}
    """

    def __init__(self, category, idType, name=None):
        self.category = category
        self.type = idType
        self.name = name


    def toElement(self):
        """
        Generate a DOM representation.

        @rtype: L{domish.Element}.
        """
        element = domish.Element((NS_DISCO_INFO, 'identity'))
        if self.category:
            element['category'] = self.category
        if self.type:
            element['type'] = self.type
        if self.name:
            element['name'] = self.name
        return element


    @staticmethod
    def fromElement(element):
        """
        Parse a DOM representation into a L{DiscoIdentity} instance.

        @param element: Element that represents the disco identity.
        @type element: L{domish.Element}.
        @rtype L{DiscoIdentity}.
        """
        category = element.getAttribute('category')
        idType = element.getAttribute('type')
        name = element.getAttribute('name')
        feature = DiscoIdentity(category, idType, name)
        return feature



class DiscoInfo(object):
    """
    XMPP service discovery info.

    @ivar nodeIdentifier: The optional node this info applies to.
    @type nodeIdentifier: C{unicode}
    @ivar features: Features as L{DiscoFeature}.
    @type features: C{set)
    @ivar identities: Identities as a mapping from (category, type) to name,
                      all C{unicode}.
    @type identities: C{dict}
    @ivar extensions: Service discovery extensions as a mapping from the
                      extension form's C{FORM_TYPE} (C{unicode}) to
                      L{data_form.Form}. Forms with no C{FORM_TYPE} field
                      are mapped as C{None}. Note that multiple forms
                      with the same C{FORM_TYPE} have the last in sequence
                      prevail.
    @type extensions: C{dict}
    @ivar _items: Sequence of added items.
    @type _items: C{list}
    """

    def __init__(self):
        self.nodeIdentifier = ''
        self.features = set()
        self.identities = {}
        self.extensions = {}
        self._items = []


    def __iter__(self):
        """
        Iterator over sequence of items in the order added.
        """
        return iter(self._items)


    def append(self, item):
        """
        Add a piece of service discovery info.

        @param item: A feature, identity or extension form.
        @type item: L{DiscoFeature}, L{DiscoIdentity} or L{data_form.Form}
        """
        self._items.append(item)

        if isinstance(item, DiscoFeature):
            self.features.add(item)
        elif isinstance(item, DiscoIdentity):
            self.identities[(item.category, item.type)] = item.name
        elif isinstance(item, data_form.Form):
            self.extensions[item.formNamespace] = item


    def toElement(self):
        """
        Generate a DOM representation.

        This takes the items added with C{append} to create a DOM
        representation of service discovery information.

        @rtype: L{domish.Element}.
        """
        element = domish.Element((NS_DISCO_INFO, 'query'))

        if self.nodeIdentifier:
            element['node'] = self.nodeIdentifier

        for item in self:
            element.addChild(item.toElement())

        return element


    @staticmethod
    def fromElement(element):
        """
        Parse a DOM representation into a L{DiscoInfo} instance.

        @param element: Element that represents the disco info.
        @type element: L{domish.Element}.
        @rtype L{DiscoInfo}.
        """

        info = DiscoInfo()

        info.nodeIdentifier = element.getAttribute('node', '')

        for child in element.elements():
            item = None

            if (child.uri, child.name) == (NS_DISCO_INFO, 'feature'):
                item = DiscoFeature.fromElement(child)
            elif (child.uri, child.name) == (NS_DISCO_INFO, 'identity'):
                item = DiscoIdentity.fromElement(child)
            elif (child.uri, child.name) == (data_form.NS_X_DATA, 'x'):
                item = data_form.Form.fromElement(child)

            if item:
                info.append(item)

        return info



class DiscoItem(object):
    """
    XMPP service discovery item.

    @ivar entity: The entity holding the item.
    @type entity: L{jid.JID}
    @ivar nodeIdentifier: The optional node identifier for the item.
    @type nodeIdentifier: C{unicode}
    @ivar name: The optional natural language name for this entity.
    @type name: C{unicode}
    """

    def __init__(self, entity, nodeIdentifier='', name=None):
        self.entity = entity
        self.nodeIdentifier = nodeIdentifier
        self.name = name


    def toElement(self):
        """
        Generate a DOM representation.

        @rtype: L{domish.Element}.
        """
        element = domish.Element((NS_DISCO_ITEMS, 'item'))
        if self.entity:
            element['jid'] = self.entity.full()
        if self.nodeIdentifier:
            element['node'] = self.nodeIdentifier
        if self.name:
            element['name'] = self.name
        return element


    @staticmethod
    def fromElement(element):
        """
        Parse a DOM representation into a L{DiscoItem} instance.

        @param element: Element that represents the disco iitem.
        @type element: L{domish.Element}.
        @rtype L{DiscoItem}.
        """
        try:
            entity = jid.JID(element.getAttribute('jid', ' '))
        except jid.InvalidFormat:
            entity = None
        nodeIdentifier = element.getAttribute('node', '')
        name = element.getAttribute('name')
        feature = DiscoItem(entity, nodeIdentifier, name)
        return feature



class DiscoItems(object):
    """
    XMPP service discovery items.

    @ivar nodeIdentifier: The optional node this info applies to.
    @type nodeIdentifier: C{unicode}
    @ivar _items: Sequence of added items.
    @type _items: C{list}
    """

    def __init__(self):
        self.nodeIdentifier = ''
        self._items = []


    def __iter__(self):
        """
        Iterator over sequence of items in the order added.
        """
        return iter(self._items)


    def append(self, item):
        """
        Append item to the sequence of items.

        @param item: Item to be added.
        @type item: L{DiscoItem}
        """
        self._items.append(item)


    def toElement(self):
        """
        Generate a DOM representation.

        This takes the items added with C{append} to create a DOM
        representation of service discovery items.

        @rtype: L{domish.Element}.
        """
        element = domish.Element((NS_DISCO_ITEMS, 'query'))

        if self.nodeIdentifier:
            element['node'] = self.nodeIdentifier

        for item in self:
            element.addChild(item.toElement())

        return element


    @staticmethod
    def fromElement(element):
        """
        Parse a DOM representation into a L{DiscoItems} instance.

        @param element: Element that represents the disco items.
        @type element: L{domish.Element}.
        @rtype L{DiscoItems}.
        """

        info = DiscoItems()

        info.nodeIdentifier = element.getAttribute('node', '')

        for child in element.elements():
            if (child.uri, child.name) == (NS_DISCO_ITEMS, 'item'):
                item = DiscoItem.fromElement(child)
                info.append(item)

        return info



class _DiscoRequest(xmlstream.IQ):
    """
    Element representing an XMPP service discovery request.
    """

    def __init__(self, xs, namespace, nodeIdentifier=''):
        """
        Initialize the request.

        @param xs: XML Stream the request should go out on.
        @type xs: L{xmlstream.XmlStream}
        @param namespace: Request namespace.
        @type namespace: C{str}
        @param nodeIdentifier: Node to request info from.
        @type nodeIdentifier: C{unicode}
        """
        xmlstream.IQ.__init__(self, xs, "get")
        query = self.addElement((namespace, 'query'))
        if nodeIdentifier:
            query['node'] = nodeIdentifier



class DiscoClientProtocol(XMPPHandler):
    """
    XMPP Service Discovery client protocol.
    """

    def requestInfo(self, entity, nodeIdentifier=''):
        """
        Request information discovery from a node.

        @param entity: Entity to send the request to.
        @type entity: L{jid.JID}
        @param nodeIdentifier: Optional node to request info from.
        @type nodeIdentifier: C{unicode}
        """

        request = _DiscoRequest(self.xmlstream, NS_DISCO_INFO, nodeIdentifier)

        d = request.send(entity.full())
        d.addCallback(lambda iq: DiscoInfo.fromElement(iq.query))
        return d


    def requestItems(self, entity, nodeIdentifier=''):
        """
        Request items discovery from a node.

        @param entity: Entity to send the request to.
        @type entity: L{jid.JID}
        @param nodeIdentifier: Optional node to request info from.
        @type nodeIdentifier: C{unicode}
        """

        request = _DiscoRequest(self.xmlstream, NS_DISCO_ITEMS, nodeIdentifier)

        d = request.send(entity.full())
        d.addCallback(lambda iq: DiscoItems.fromElement(iq.query))
        return d



class DiscoHandler(XMPPHandler, IQHandlerMixin):
    """
    Protocol implementation for XMPP Service Discovery.

    This handler will listen to XMPP service discovery requests and
    query the other handlers in L{parent} (see L{XMPPHandlerContainer}) for
    their identities, features and items according to L{IDisco}.
    """

    iqHandlers = {DISCO_INFO: '_onDiscoInfo',
                  DISCO_ITEMS: '_onDiscoItems'}

    def connectionInitialized(self):
        self.xmlstream.addObserver(DISCO_INFO, self.handleRequest)
        self.xmlstream.addObserver(DISCO_ITEMS, self.handleRequest)


    def _onDiscoInfo(self, iq):
        """
        Called for incoming disco info requests.

        @param iq: The request iq element.
        @type iq: L{Element<twisted.words.xish.domish.Element>}
        """
        requestor = jid.internJID(iq["from"])
        target = jid.internJID(iq["to"])
        nodeIdentifier = iq.query.getAttribute("node", '')

        def toResponse(info):
            if nodeIdentifier and not info:
                raise error.StanzaError('item-not-found')
            else:
                response = DiscoInfo()
                response.nodeIdentifier = nodeIdentifier

                for item in info:
                    response.append(item)

            return response.toElement()

        d = self.info(requestor, target, nodeIdentifier)
        d.addCallback(toResponse)
        return d


    def _onDiscoItems(self, iq):
        """
        Called for incoming disco items requests.

        @param iq: The request iq element.
        @type iq: L{Element<twisted.words.xish.domish.Element>}
        """
        requestor = jid.internJID(iq["from"])
        target = jid.internJID(iq["to"])
        nodeIdentifier = iq.query.getAttribute("node", '')

        def toResponse(items):
            response = DiscoItems()
            response.nodeIdentifier = nodeIdentifier

            for item in items:
                response.append(item)

            return response.toElement()

        d = self.items(requestor, target, nodeIdentifier)
        d.addCallback(toResponse)
        return d


    def _gatherResults(self, deferredList):
        """
        Gather results from a list of deferreds.

        Similar to L{defer.gatherResults}, but flattens the returned results,
        consumes errors after the first one and fires the errback of the
        returned deferred with the failure of the first deferred that fires its
        errback.

        @param deferredList: List of deferreds for which the results should be
                             gathered.
        @type deferredList: C{list}
        @return: Deferred that fires with a list of gathered results.
        @rtype: L{defer.Deferred}
        """
        def cb(resultList):
            results = []
            for success, value in resultList:
                results.extend(value)
            return results

        def eb(failure):
            failure.trap(defer.FirstError)
            return failure.value.subFailure

        d = defer.DeferredList(deferredList, fireOnOneErrback=1,
                                             consumeErrors=1)
        d.addCallbacks(cb, eb)
        return d


    def info(self, requestor, target, nodeIdentifier):
        """
        Inspect all sibling protocol handlers for disco info.

        Calls the L{getDiscoInfo<IDisco.getDiscoInfo>} method on all child
        handlers of the parent, that provide L{IDisco}.

        @param requestor: The entity that sent the request.
        @type requestor: L{JID<twisted.words.protocols.jabber.jid.JID>}
        @param target: The entity the request was sent to.
        @type target: L{JID<twisted.words.protocols.jabber.jid.JID>}
        @param nodeIdentifier: The optional node being queried, or C{''}.
        @type nodeIdentifier: C{unicode}
        @return: Deferred with the gathered results from sibling handlers.
        @rtype: L{defer.Deferred}
        """
        dl = [handler.getDiscoInfo(requestor, target, nodeIdentifier)
              for handler in self.parent
              if IDisco.providedBy(handler)]
        return self._gatherResults(dl)


    def items(self, requestor, target, nodeIdentifier):
        """
        Inspect all sibling protocol handlers for disco items.

        Calls the L{getDiscoItems<IDisco.getDiscoItems>} method on all child
        handlers of the parent, that provide L{IDisco}.

        @param requestor: The entity that sent the request.
        @type requestor: L{JID<twisted.words.protocols.jabber.jid.JID>}
        @param target: The entity the request was sent to.
        @type target: L{JID<twisted.words.protocols.jabber.jid.JID>}
        @param nodeIdentifier: The optional node being queried, or C{''}.
        @type nodeIdentifier: C{unicode}
        @return: Deferred with the gathered results from sibling handlers.
        @rtype: L{defer.Deferred}
        """
        dl = [handler.getDiscoItems(requestor, target, nodeIdentifier)
              for handler in self.parent
              if IDisco.providedBy(handler)]
        return self._gatherResults(dl)
