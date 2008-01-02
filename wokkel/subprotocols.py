# -*- test-case-name: wokkel.test.test_subprotocols -*-
#
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
XMPP subprotocol support.
"""

from zope.interface import implements

from twisted.internet import defer
from twisted.python import log
from twisted.words.protocols.jabber import error, xmlstream
from twisted.words.xish import xpath
from twisted.words.xish.domish import IElement

try:
    from twisted.words.protocols.jabber.xmlstream import toResponse
except ImportError:
    from wokkel.compat import toResponse

from wokkel.iwokkel import IXMPPHandler, IXMPPHandlerCollection

class XMPPHandler(object):
    implements(IXMPPHandler)

    def setHandlerParent(self, parent):
        self.parent = parent
        self.parent.addHandler(self)

    def disownHandlerParent(self, parent):
        self.parent.removeHandler(self)
        self.parent = None

    def makeConnection(self, xs):
        self.xmlstream = xs
        self.connectionMade()

    def connectionMade(self):
        pass

    def connectionInitialized(self):
        pass

    def connectionLost(self, reason):
        self.xmlstream = None

    def send(self, obj):
        """
        Send data over the managed XML stream.

        @note: The stream manager maintains a queue for data sent using this
               method when there is no current initialized XML stream. This
               data is then sent as soon as a new stream has been established
               and initialized. Subsequently, L{connectionInitialized} will be
               called again. If this queueing is not desired, use C{send} on
               C{self.xmlstream}.

        @param obj: data to be sent over the XML stream. This is usually an
                    object providing L{domish.IElement}, or serialized XML. See
                    L{xmlstream.XmlStream} for details.
        """
        self.parent.send(obj)


class XMPPHandlerCollection(object):
    """
    Collection of XMPP subprotocol handlers.

    This allows for grouping of subprotocol handlers, but is not an
    L{XMPPHandler} itself, so this is not recursive.

    @ivar xmlstream: Currently managed XML stream.
    @type xmlstream: L{XmlStream}
    @ivar handlers: List of protocol handlers.
    @type handlers: L{list} of objects providing
                      L{IXMPPHandler}
    """

    implements(IXMPPHandlerCollection)

    def __init__(self):
        self.handlers = []
        self.xmlstream = None
        self._initialized = False

    def __iter__(self):
        """
        Act as a container for handlers.
        """
        return iter(self.handlers)

    def addHandler(self, handler):
        """
        Add protocol handler.

        Protocol handlers are expected to provide L{IXMPPHandler}.

        When an XML stream has already been established, the handler's
        C{connectionInitialized} will be called to get it up to speed.
        """

        self.handlers.append(handler)

        # get protocol handler up to speed when a connection has already
        # been established
        if self.xmlstream and self._initialized:
            handler.makeConnection(self.xmlstream)
            handler.connectionInitialized()

    def removeHandler(self, handler):
        """
        Remove protocol handler.
        """

        self.handlers.remove(handler)

class StreamManager(XMPPHandlerCollection):
    """
    Business logic representing a managed XMPP connection.

    This maintains a single XMPP connection and provides facilities for packet
    routing and transmission. Business logic modules are objects providing
    L{IXMPPHandler} (like subclasses of L{XMPPHandler}), and added
    using L{addHandler}.

    @ivar logTraffic: if true, log all traffic.
    @type logTraffic: L{bool}
    @ivar _packetQueue: internal buffer of unsent data. See L{send} for details.
    @type _packetQueue: L{list}
    """

    logTraffic = False

    def __init__(self, factory):
        self.handlers = []
        self.xmlstream = None
        self._packetQueue = []
        self._initialized = False

        factory.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT, self._connected)
        factory.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self._authd)
        factory.addBootstrap(xmlstream.INIT_FAILED_EVENT,
                             self.initializationFailed)
        factory.addBootstrap(xmlstream.STREAM_END_EVENT, self._disconnected)
        self.factory = factory

    def _connected(self, xs):
        def logDataIn(buf):
            log.msg("RECV: %r" % buf)

        def logDataOut(buf):
            log.msg("SEND: %r" % buf)

        if self.logTraffic:
            xs.rawDataInFn = logDataIn
            xs.rawDataOutFn = logDataOut

        self.xmlstream = xs

        for e in self:
            e.makeConnection(xs)

    def _authd(self, xs):
        # Flush all pending packets
        for p in self._packetQueue:
            xs.send(p)
        self._packetQueue = []
        self._initialized = True

        # Notify all child services which implement
        # the IService interface
        for e in self:
            e.connectionInitialized()

    def initializationFailed(self, reason):
        """
        Called when stream initialization has failed.

        Stream initialization has halted, with the reason indicated by
        C{reason}. It may be retried by calling the authenticator's
        C{initializeStream}. See the respective authenticators for details.

        @param reason: A failure instance indicating why stream initialization
                       failed.
        @type reason: L{failure.Failure}
        """

    def _disconnected(self, _):
        self.xmlstream = None
        self._initialized = False

        # Notify all child services which implement
        # the IService interface
        for e in self:
            e.xmlstream = None
            e.connectionLost(None)

    def send(self, obj):
        """
        Send data over the XML stream.

        When there is no established XML stream, the data is queued and sent
        out when a new XML stream has been established and initialized.

        @param obj: data to be sent over the XML stream. See
                    L{xmlstream.XmlStream.send} for details.
        """

        if self._initialized:
            self.xmlstream.send(obj)
        else:
            self._packetQueue.append(obj)


class IQHandlerMixin(object):
    """
    XMPP subprotocol mixin for handle incoming IQ stanzas.

    This matches up the iq with XPath queries to call methods on itself,
    wrapping the call so that exceptions result in proper error responses,
    or, when succesful will reply with a response with optional payload.

    Derivatives of this class must provide an
    L{XmlStream<twisted.words.protocols.jabber.xmlstream.XmlStream>} instance
    in its C{xmlstream} attribute.

    The optional payload is taken from the result of the handler and is
    expected to be a child or a list of childs.

    If an exception is raised, or the deferred has its errback called,
    the exception is checked for being a L{error.StanzaError}. If so,
    an error response is sent. Any other exception will cause a error
    response of C{internal-server-error} to be sent.

    @cvar iqHandlers: Mapping from XPath queries (as a string) to the method
                      name that will handle requests that match the query.
    @type iqHandlers: L{dict}
    """

    iqHandlers = None

    def handleRequest(self, iq):
        """
        Find a handler and wrap the call for sending a response stanza.
        """
        def toResult(result, iq):
            response = toResponse(iq, 'result')

            if result:
                if IElement.providedBy(result):
                    response.addChild(result)
                else:
                    for element in result:
                        response.addChild(element)

            return response

        def checkNotImplemented(failure):
            failure.trap(NotImplementedError)
            raise error.StanzaError('feature-not-implemented')

        def fromStanzaError(failure, iq):
            e = failure.trap(error.StanzaError)
            return failure.value.toResponse(iq)

        def fromOtherError(failure, iq):
            log.msg("Unhandled error in iq handler:", isError=True)
            log.err(failure)
            return error.StanzaError('internal-server-error').toResponse(iq)

        handler = None
        for queryString, method in self.iqHandlers.iteritems():
            if xpath.internQuery(queryString).matches(iq):
                handler = getattr(self, method)

        if handler:
            d = defer.maybeDeferred(handler, iq)
        else:
            d = defer.fail(NotImplementedError())

        d.addCallback(toResult, iq)
        d.addErrback(checkNotImplemented)
        d.addErrback(fromStanzaError, iq)
        d.addErrback(fromOtherError, iq)

        d.addCallback(self.send)

        iq.handled = True
