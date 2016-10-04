# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Unit test helpers.
"""

from __future__ import division, absolute_import

from twisted.internet import defer
from twisted.python.compat import iteritems
from twisted.words.xish import xpath
from twisted.words.xish.utility import EventDispatcher

from wokkel.generic import parseXml
from wokkel.subprotocols import StreamManager

class XmlStreamStub(object):
    """
    Stub for testing objects that communicate through XML Streams.

    Instances of this stub hold an object in L{xmlstream} that acts like an
    L{XmlStream<twisted.words.xish.xmlstream.XmlStream} after connection stream
    initialization. Stanzas can be sent through it by calling its C{send}
    method with an object implementing
    L{IElement<twisted.words.xish.domish.IElement>} as its first argument.
    These appear in sequence in the L{output} instance variable of the stub.

    For the reverse direction, stanzas passed to L{send} of the stub, will be
    dispatched in the stubbed XmlStream as if it was received over the wire, so
    that registered observers will be called.

    Example::

        >>> stub = XmlStreamStub()
        >>> stub.xmlstream.send(domish.Element((None, 'presence')))
        >>> stub.output[-1].toXml()
        u'<presence/>'
        >>> def cb(stanza):
        ...     print("Got: %r" stanza.toXml())
        >>> stub.xmlstream.addObserver('/presence')
        >>> stub.send(domish.Element((None, 'presence')))
        Got: u'<presence/>'

    @ivar xmlstream: Stubbed XML Stream.
    @type xmlstream: L{EventDispatcher}
    @ivar output: List of stanzas sent to the XML Stream.
    @type output: L{list}
    """

    def __init__(self):
        self.output = []
        self.xmlstream = EventDispatcher()
        self.xmlstream.send = self.output.append

    def send(self, obj):
        """
        Pass an element to the XML Stream as if received.

        @param obj: Element to be dispatched to C{self.xmlstream}.
        @type obj: object implementing
                   L{IElement<twisted.words.xish.domish.IElement>}.
        """
        self.xmlstream.dispatch(obj)


class TestableRequestHandlerMixin(object):
    """
    Mixin for testing XMPPHandlers that process iq requests.

    Handlers that use L{wokkel.subprotocols.IQHandlerMixin} define a
    C{iqHandlers} attribute that lists the handlers to be called for iq
    requests. This mixin provides L{handleRequest} to mimic the handler
    processing for easier testing.
    """

    def handleRequest(self, xml):
        """
        Find a handler and call it directly.

        @param xml: XML stanza that may yield a handler being called.
        @type xml: C{str}.
        @return: Deferred that fires with the result of a handler for this
                 stanza. If no handler was found, the deferred has its errback
                 called with a C{NotImplementedError} exception.
        """
        handler = None
        iq = parseXml(xml)
        for queryString, method in iteritems(self.service.iqHandlers):
            if xpath.internQuery(queryString).matches(iq):
                handler = getattr(self.service, method)

        if handler:
            d = defer.maybeDeferred(handler, iq)
        else:
            d = defer.fail(NotImplementedError())

        return d


class TestableStreamManager(StreamManager):
    """
    Stream manager for testing subprotocol handlers.
    """

    def __init__(self, reactor=None):
        class DummyFactory(object):
            def addBootstrap(self, event, fn):
                pass

        factory = DummyFactory()
        StreamManager.__init__(self, factory, reactor)
        self.stub = XmlStreamStub()
        self._connected(self.stub.xmlstream)
        self._authd(self.stub.xmlstream)
