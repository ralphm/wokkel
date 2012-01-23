# -*- test-case-name: wokkel.test.test_ping -*-
#
# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
XMPP Ping.

The XMPP Ping protocol is documented in
U{XEP-0199<http://xmpp.org/extensions/xep-0199.html>}.
"""

from zope.interface import implements

from twisted.words.protocols.jabber.error import StanzaError
from twisted.words.protocols.jabber.xmlstream import IQ, toResponse
from twisted.words.protocols.jabber.xmlstream import XMPPHandler

from wokkel import disco, iwokkel

NS_PING = 'urn:xmpp:ping'
PING_REQUEST = "/iq[@type='get']/ping[@xmlns='%s']" % NS_PING

class PingClientProtocol(XMPPHandler):
    """
    Ping client.

    This handler implements the protocol for sending out XMPP Ping requests.
    """

    def ping(self, entity, sender=None):
        """
        Send out a ping request and wait for a response.

        @param entity: Entity to be pinged.
        @type entity: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @return: A deferred that fires upon receiving a response.
        @rtype: L{Deferred<twisted.internet.defer.Deferred>}

        @param sender: Optional sender address.
        @type sender: L{JID<twisted.words.protocols.jabber.jid.JID>}
        """
        def cb(response):
            return None

        def eb(failure):
            failure.trap(StanzaError)
            exc = failure.value
            if exc.condition == 'service-unavailable':
                return None
            else:
                return failure

        request = IQ(self.xmlstream, 'get')
        request.addElement((NS_PING, 'ping'))

        if sender is not None:
            request['from'] = unicode(sender)

        d = request.send(entity.full())
        d.addCallbacks(cb, eb)
        return d



class PingHandler(XMPPHandler):
    """
    Ping responder.

    This handler waits for XMPP Ping requests and sends a response.
    """

    implements(iwokkel.IDisco)

    def connectionInitialized(self):
        """
        Called when the XML stream has been initialized.

        This sets up an observer for incoming ping requests.
        """
        self.xmlstream.addObserver(PING_REQUEST, self.onPing)


    def onPing(self, iq):
        """
        Called when a ping request has been received.

        This immediately replies with a result response.
        """
        response = toResponse(iq, 'result')
        self.xmlstream.send(response)
        iq.handled = True


    def getDiscoInfo(self, requestor, target, nodeIdentifier=''):
        """
        Get identity and features from this entity, node.

        This handler supports XMPP Ping, but only without a nodeIdentifier
        specified.
        """
        if not nodeIdentifier:
            return [disco.DiscoFeature(NS_PING)]
        else:
            return []


    def getDiscoItems(self, requestor, target, nodeIdentifier=''):
        """
        Get contained items for this entity, node.

        This handler does not support items.
        """
        return []
