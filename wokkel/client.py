# -*- test-case-name: wokkel.test.test_client -*-
#
# Copyright (c) 2003-2007 Ralph Meijer
# See LICENSE for details.

"""
XMPP Client support.

This module holds several improvements on top of Twisted's XMPP support
that should probably eventually move there.
"""

from twisted.application import service
from twisted.internet import reactor
from twisted.names.srvconnect import SRVConnector
from twisted.words.protocols.jabber import client, sasl, xmlstream

from wokkel import generic
from wokkel.subprotocols import StreamManager

class CheckAuthInitializer(object):
    """
    Check what authentication methods are available.
    """

    def __init__(self, xs):
        self.xmlstream = xs

    def initialize(self):
        if (sasl.NS_XMPP_SASL, 'mechanisms') in self.xmlstream.features:
            inits = [(sasl.SASLInitiatingInitializer, True),
                     (client.BindInitializer, True),
                     (client.SessionInitializer, False)]

            for initClass, required in inits:
                init = initClass(self.xmlstream)
                init.required = required
                self.xmlstream.initializers.append(init)
        elif (client.NS_IQ_AUTH_FEATURE, 'auth') in self.xmlstream.features:
            self.xmlstream.initializers.append(
                    client.IQAuthInitializer(self.xmlstream))
        else:
            raise Exception("No available authentication method found")


class HybridAuthenticator(xmlstream.ConnectAuthenticator):
    """
    Initializes an XmlStream connecting to an XMPP server as a Client.

    This is similar to L{client.XMPPAuthenticator}, but also tries non-SASL
    autentication.
    """

    namespace = 'jabber:client'

    def __init__(self, jid, password):
        xmlstream.ConnectAuthenticator.__init__(self, jid.host)
        self.jid = jid
        self.password = password

    def associateWithStream(self, xs):
        xmlstream.ConnectAuthenticator.associateWithStream(self, xs)

        tlsInit = xmlstream.TLSInitiatingInitializer(xs)
        xs.initializers = [client.CheckVersionInitializer(xs),
                           tlsInit,
                           CheckAuthInitializer(xs)]


def HybridClientFactory(jid, password):
    """
    Client factory for XMPP 1.0.

    This is similar to L{client.XMPPClientFactory} but also tries non-SASL
    autentication.
    """

    a = HybridAuthenticator(jid, password)
    return xmlstream.XmlStreamFactory(a)


class XMPPClient(StreamManager, service.Service):
    """
    Service that initiates an XMPP client connection.
    """

    def __init__(self, jid, password, host=None, port=5222):
        self.domain = jid.host
        self.host = host
        self.port = port

        factory = HybridClientFactory(jid, password)

        StreamManager.__init__(self, factory)

    def startService(self):
        service.Service.startService(self)

        self._connection = self._getConnection()

    def stopService(self):
        service.Service.stopService(self)

        self.factory.stopTrying()
        self._connection.disconnect()

    def initializationFailed(self, reason):
        """
        Called when stream initialization has failed.

        Stop the service (thereby disconnecting the current stream) and
        raise the exception.
        """
        self.stopService()
        reason.raiseException()

    def _getConnection(self):
        if self.host:
            return reactor.connectTCP(self.host, self.port, self.factory)
        else:
            c = SRVConnector(reactor, 'xmpp-client', self.domain, self.factory)
            c.connect()
            return c


class DeferredClientFactory(generic.DeferredXmlStreamFactory):

    def __init__(self, jid, password):
        authenticator = client.XMPPAuthenticator(jid, password)
        generic.DeferredXmlStreamFactory.__init__(self, authenticator)


    def addHandler(self, handler):
        """
        Add a subprotocol handler to the stream manager.
        """
        self.streamManager.addHandler(handler)


    def removeHandler(self, handler):
        """
        Add a subprotocol handler to the stream manager.
        """
        self.streamManager.removeHandler(handler)



def clientCreator(factory):
    domain = factory.authenticator.jid.host
    c = SRVConnector(reactor, 'xmpp-client', domain, factory)
    c.connect()
    return factory.deferred
