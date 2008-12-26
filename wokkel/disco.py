# -*- test-case-name: wokkel.test.test_disco -*-
#
# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
XMPP Service Discovery.

The XMPP service discovery protocol is documented in
U{XEP-0030<http://www.xmpp.org/extensions/xep-0030.html>}.
"""

from twisted.internet import defer
from twisted.words.protocols.jabber import error, jid
from twisted.words.xish import domish

from wokkel.iwokkel import IDisco
from wokkel.subprotocols import IQHandlerMixin, XMPPHandler

NS_DISCO = 'http://jabber.org/protocol/disco'
NS_DISCO_INFO = NS_DISCO + '#info'
NS_DISCO_ITEMS = NS_DISCO + '#items'

IQ_GET = '/iq[@type="get"]'
DISCO_INFO = IQ_GET + '/query[@xmlns="' + NS_DISCO_INFO + '"]'
DISCO_ITEMS = IQ_GET + '/query[@xmlns="' + NS_DISCO_ITEMS + '"]'

class DiscoFeature(domish.Element):
    """
    Element representing an XMPP service discovery feature.
    """

    def __init__(self, feature):
        domish.Element.__init__(self, (NS_DISCO_INFO, 'feature'),
                                attribs={'var': feature})


class DiscoIdentity(domish.Element):
    """
    Element representing an XMPP service discovery identity.
    """

    def __init__(self, category, type, name = None):
        domish.Element.__init__(self, (NS_DISCO_INFO, 'identity'),
                                attribs={'category': category,
                                         'type': type})
        if name:
            self['name'] = name


class DiscoItem(domish.Element):
    """
    Element representing an XMPP service discovery item.
    """

    def __init__(self, jid, node='', name=None):
        domish.Element.__init__(self, (NS_DISCO_ITEMS, 'item'),
                                attribs={'jid': jid.full()})
        if node:
            self['node'] = node

        if name:
            self['name'] = name



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
                response = domish.Element((NS_DISCO_INFO, 'query'))
                if nodeIdentifier:
                    response['node'] = nodeIdentifier

                for item in info:
                    response.addChild(item)

            return response

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
            response = domish.Element((NS_DISCO_ITEMS, 'query'))
            if nodeIdentifier:
                response['node'] = nodeIdentifier

            for item in items:
                response.addChild(item)

            return response

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
