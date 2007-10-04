# -*- test-case-name: wokkel.test.test_disco -*-
#
# Copyright (c) 2003-2007 Ralph Meijer
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

NS = 'http://jabber.org/protocol/disco'
NS_INFO = NS + '#info'
NS_ITEMS = NS + '#items'

IQ_GET = '/iq[@type="get"]'
DISCO_INFO = IQ_GET + '/query[@xmlns="' + NS_INFO + '"]'
DISCO_ITEMS = IQ_GET + '/query[@xmlns="' + NS_ITEMS + '"]'

class DiscoFeature(domish.Element):
    """
    Element representing an XMPP service discovery feature.
    """

    def __init__(self, feature):
        domish.Element.__init__(self, (NS_INFO, 'feature'),
                                attribs={'var': feature})


class DiscoIdentity(domish.Element):
    """
    Element representing an XMPP service discovery identity.
    """

    def __init__(self, category, type, name = None):
        domish.Element.__init__(self, (NS_INFO, 'identity'),
                                attribs={'category': category,
                                         'type': type})
        if name:
            self['name'] = name


class DiscoItem(domish.Element):
    """
    Element representing an XMPP service discovery item.
    """

    def __init__(self, jid, node = None, name = None):
        domish.Element.__init__(self, (NS_ITEMS, 'item'),
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

    def _error(self, failure):
        failure.trap(defer.FirstError)
        return failure.value.subFailure

    def _onDiscoInfo(self, iq):
        requestor = jid.internJID(iq["from"])
        target = jid.internJID(iq["to"])
        nodeIdentifier = iq.query.getAttribute("node")

        def toResponse(results):
            info = []
            for i in results:
                info.extend(i[1])

            if nodeIdentifier and not info:
                raise error.StanzaError('item-not-found')
            else:
                response = domish.Element((NS_INFO, 'query'))

                for item in info:
                    response.addChild(item)

            return response

        dl = []
        for handler in self.parent:
            if IDisco.providedBy(handler):
                dl.append(handler.getDiscoInfo(requestor, target,
                                               nodeIdentifier))

        d = defer.DeferredList(dl, fireOnOneErrback=1, consumeErrors=1)
        d.addCallbacks(toResponse, self._error)
        return d

    def _onDiscoItems(self, iq):
        requestor = jid.internJID(iq["from"])
        target = jid.internJID(iq["to"])
        nodeIdentifier = iq.query.getAttribute("node")

        def toResponse(results):
            items = []
            for i in results:
                items.extend(i[1])

            response = domish.Element((NS_ITEMS, 'query'))

            for item in items:
                response.addChild(item)

            return response

        dl = []
        for handler in self.parent:
            if IDisco.providedBy(handler):
                dl.append(handler.getDiscoItems(requestor, target,
                                                nodeIdentifier))

        d = defer.DeferredList(dl, fireOnOneErrback=1, consumeErrors=1)
        d.addCallbacks(toResponse, self._error)
        return d
