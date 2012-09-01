# -*- test-case-name: wokkel.test.test_component -*-
#
# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
XMPP External Component utilities.
"""

from twisted.application import service
from twisted.internet import reactor
from twisted.python import log
from twisted.words.protocols.jabber.jid import internJID as JID
from twisted.words.protocols.jabber import component, error, xmlstream
from twisted.words.xish import domish

from wokkel.generic import XmlPipe
from wokkel.subprotocols import StreamManager

NS_COMPONENT_ACCEPT = 'jabber:component:accept'

class Component(StreamManager, service.Service):
    """
    XMPP External Component service.

    This service is a XMPP stream manager that connects as an External
    Component to an XMPP server, as described in
    U{XEP-0114<http://xmpp.org/extensions/xep-0114.html>}.
    """
    def __init__(self, host, port, jid, password):
        self.host = host
        self.port = port

        factory = component.componentFactory(jid, password)

        StreamManager.__init__(self, factory)


    def _authd(self, xs):
        """
        Called when stream initialization has completed.

        This replaces the C{send} method of the C{XmlStream} instance
        that represents the current connection so that outgoing stanzas
        always have a from attribute set to the JID of the component.
        """
        old_send = xs.send

        def send(obj):
            if domish.IElement.providedBy(obj) and \
                    not obj.getAttribute('from'):
                obj['from'] = self.xmlstream.thisEntity.full()
            old_send(obj)

        xs.send = send
        StreamManager._authd(self, xs)


    def initializationFailed(self, reason):
        """
        Called when stream initialization has failed.

        Stop the service (thereby disconnecting the current stream) and
        raise the exception.
        """
        self.stopService()
        reason.raiseException()


    def startService(self):
        """
        Start the service and connect to the server.
        """
        service.Service.startService(self)

        self._connection = self._getConnection()


    def stopService(self):
        """
        Stop the service, close the connection and prevent reconnects.
        """
        service.Service.stopService(self)

        self.factory.stopTrying()
        self._connection.disconnect()


    def _getConnection(self):
        """
        Create a connector that connects to the server.
        """
        return reactor.connectTCP(self.host, self.port, self.factory)



class InternalComponent(xmlstream.XMPPHandlerCollection, service.Service):
    """
    Component service that connects directly to a router.

    Instead of opening a socket to connect to a router, like L{Component},
    components of this type connect to a router in the same process. This
    allows for one-process XMPP servers.

    @ivar domains: Domains (as C{str}) this component will handle traffic for.
    @type domains: C{set}
    """

    def __init__(self, router, domain=None):
        xmlstream.XMPPHandlerCollection.__init__(self)

        self._router = router
        self.domains = set()
        if domain:
            self.domains.add(domain)

        self.xmlstream = None

    def startService(self):
        """
        Create a XML pipe, connect to the router and setup handlers.
        """
        service.Service.startService(self)

        self._pipe = XmlPipe()
        self.xmlstream = self._pipe.source

        for domain in self.domains:
            self._router.addRoute(domain, self._pipe.sink)

        for e in self:
            e.makeConnection(self.xmlstream)
            e.connectionInitialized()


    def stopService(self):
        """
        Disconnect from the router and handlers.
        """
        service.Service.stopService(self)

        for domain in self.domains:
            self._router.removeRoute(domain, self._pipe.sink)

        self._pipe = None
        self.xmlstream = None

        for e in self:
            e.connectionLost(None)


    def addHandler(self, handler):
        """
        Add a new handler and connect it to the stream.
        """
        xmlstream.XMPPHandlerCollection.addHandler(self, handler)

        if self.xmlstream:
            handler.makeConnection(self.xmlstream)
            handler.connectionInitialized()


    def send(self, obj):
        """
        Send data to the XML stream, so it ends up at the router.
        """
        self.xmlstream.send(obj)



class ListenComponentAuthenticator(xmlstream.ListenAuthenticator):
    """
    Authenticator for accepting components.

    @ivar secret: The shared used to authorized incoming component connections.
    @type secret: C{unicode}.
    """

    namespace = NS_COMPONENT_ACCEPT

    def __init__(self, secret):
        self.secret = secret
        xmlstream.ListenAuthenticator.__init__(self)


    def associateWithStream(self, xs):
        """
        Associate the authenticator with a stream.

        This sets the stream's version to 0.0, because the XEP-0114 component
        protocol was not designed for XMPP 1.0.
        """
        xs.version = (0, 0)
        xmlstream.ListenAuthenticator.associateWithStream(self, xs)


    def streamStarted(self, rootElement):
        """
        Called by the stream when it has started.

        This examines the default namespace of the incoming stream and whether
        there is a requested hostname for the component. Then it generates a
        stream identifier, sends a response header and adds an observer for
        the first incoming element, triggering L{onElement}.
        """

        xmlstream.ListenAuthenticator.streamStarted(self, rootElement)

        # Compatibility fix for pre-8.2 implementations of ListenAuthenticator
        if not self.xmlstream.sid:
            from twisted.python import randbytes
            self.xmlstream.sid = randbytes.secureRandom(8).encode('hex')

        if rootElement.defaultUri != self.namespace:
            exc = error.StreamError('invalid-namespace')
            self.xmlstream.sendStreamError(exc)
            return

        # self.xmlstream.thisEntity is set to the address the component
        # wants to assume.
        if not self.xmlstream.thisEntity:
            exc = error.StreamError('improper-addressing')
            self.xmlstream.sendStreamError(exc)
            return

        self.xmlstream.sendHeader()
        self.xmlstream.addOnetimeObserver('/*', self.onElement)


    def onElement(self, element):
        """
        Called on incoming XML Stanzas.

        The very first element received should be a request for handshake.
        Otherwise, the stream is dropped with a 'not-authorized' error. If a
        handshake request was received, the hash is extracted and passed to
        L{onHandshake}.
        """
        if (element.uri, element.name) == (self.namespace, 'handshake'):
            self.onHandshake(unicode(element))
        else:
            exc = error.StreamError('not-authorized')
            self.xmlstream.sendStreamError(exc)


    def onHandshake(self, handshake):
        """
        Called upon receiving the handshake request.

        This checks that the given hash in C{handshake} is equal to a
        calculated hash, responding with a handshake reply or a stream error.
        If the handshake was ok, the stream is authorized, and  XML Stanzas may
        be exchanged.
        """
        calculatedHash = xmlstream.hashPassword(self.xmlstream.sid,
                                                unicode(self.secret))
        if handshake != calculatedHash:
            exc = error.StreamError('not-authorized', text='Invalid hash')
            self.xmlstream.sendStreamError(exc)
        else:
            self.xmlstream.send('<handshake/>')
            self.xmlstream.dispatch(self.xmlstream,
                                    xmlstream.STREAM_AUTHD_EVENT)



class Router(object):
    """
    XMPP Server's Router.

    A router connects the different components of the XMPP service and routes
    messages between them based on the given routing table.

    Connected components are trusted to have correct addressing in the
    stanzas they offer for routing.

    A route destination of C{None} adds a default route. Traffic for which no
    specific route exists, will be routed to this default route.

    @ivar routes: Routes based on the host part of JIDs. Maps host names to the
        L{EventDispatcher<twisted.words.xish.utility.EventDispatcher>}s that
        should receive the traffic. A key of C{None} means the default route.
    @type routes: C{dict}
    """

    def __init__(self):
        self.routes = {}


    def addRoute(self, destination, xs):
        """
        Add a new route.

        The passed XML Stream C{xs} will have an observer for all stanzas
        added to route its outgoing traffic. In turn, traffic for
        C{destination} will be passed to this stream.

        @param destination: Destination of the route to be added as a host name
                            or C{None} for the default route.
        @type destination: C{str} or C{NoneType}

        @param xs: XML Stream to register the route for.
        @type xs:
            L{EventDispatcher<twisted.words.xish.utility.EventDispatcher>}
        """
        self.routes[destination] = xs
        xs.addObserver('/*', self.route)


    def removeRoute(self, destination, xs):
        """
        Remove a route.

        @param destination: Destination of the route that should be removed.
        @type destination: C{str}.

        @param xs: XML Stream to remove the route for.
        @type xs:
            L{EventDispatcher<twisted.words.xish.utility.EventDispatcher>}
        """
        xs.removeObserver('/*', self.route)
        if (xs == self.routes[destination]):
            del self.routes[destination]


    def route(self, stanza):
        """
        Route a stanza.

        @param stanza: The stanza to be routed.
        @type stanza: L{domish.Element}.
        """
        destination = JID(stanza['to'])


        if destination.host in self.routes:
            log.msg("Routing to %s: %r" % (destination.full(),
                                           stanza.toXml()))
            self.routes[destination.host].send(stanza)
        elif None in self.routes:
            log.msg("Routing to %s (default route): %r" % (destination.full(),
                                                           stanza.toXml()))
            self.routes[None].send(stanza)
        else:
            log.msg("No route to %s: %r" % (destination.full(),
                                            stanza.toXml()))
            if stanza.getAttribute('type') not in ('result', 'error'):
                # No route, send back error
                exc = error.StanzaError('remote-server-timeout', type='wait')
                exc.code = '504'
                response = exc.toResponse(stanza)
                self.route(response)



class XMPPComponentServerFactory(xmlstream.XmlStreamServerFactory):
    """
    XMPP Component Server factory.

    This factory accepts XMPP external component connections and makes
    the router service route traffic for a component's bound domain
    to that component.
    """

    logTraffic = False

    def __init__(self, router, secret='secret'):
        self.router = router
        self.secret = secret

        def authenticatorFactory():
            return ListenComponentAuthenticator(self.secret)

        xmlstream.XmlStreamServerFactory.__init__(self, authenticatorFactory)
        self.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT,
                          self.makeConnection)
        self.addBootstrap(xmlstream.STREAM_AUTHD_EVENT,
                          self.connectionInitialized)

        self.serial = 0


    def makeConnection(self, xs):
        """
        Called when a component connection was made.

        This enables traffic debugging on incoming streams.
        """
        xs.serial = self.serial
        self.serial += 1

        def logDataIn(buf):
            log.msg("RECV (%d): %r" % (xs.serial, buf))

        def logDataOut(buf):
            log.msg("SEND (%d): %r" % (xs.serial, buf))

        if self.logTraffic:
            xs.rawDataInFn = logDataIn
            xs.rawDataOutFn = logDataOut

        xs.addObserver(xmlstream.STREAM_ERROR_EVENT, self.onError)


    def connectionInitialized(self, xs):
        """
        Called when a component has succesfully authenticated.

        Add the component to the routing table and establish a handler
        for a closed connection.
        """
        destination = xs.thisEntity.host

        self.router.addRoute(destination, xs)
        xs.addObserver(xmlstream.STREAM_END_EVENT, self.connectionLost, 0,
                                                   destination, xs)


    def onError(self, reason):
        log.err(reason, "Stream Error")


    def connectionLost(self, destination, xs, reason):
        self.router.removeRoute(destination, xs)
