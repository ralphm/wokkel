# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.subprotocols}
"""

from zope.interface.verify import verifyObject

from twisted.trial import unittest
from twisted.test import proto_helpers
from twisted.internet import defer, task
from twisted.internet.error import ConnectionDone
from twisted.python import failure
from twisted.words.xish import domish
from twisted.words.protocols.jabber import error, ijabber, xmlstream

from wokkel import generic, subprotocols

class DeprecationTest(unittest.TestCase):
    """
    Deprecation test for L{wokkel.subprotocols}.
    """

    def lookForDeprecationWarning(self, testmethod, attributeName, newName):
        """
        Importing C{testmethod} emits a deprecation warning.
        """
        warningsShown = self.flushWarnings([testmethod])
        self.assertEqual(len(warningsShown), 1)
        self.assertIdentical(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            "wokkel.subprotocols." + attributeName + " "
            "was deprecated in Wokkel 0.7.0: Use " + newName + " instead.")


    def test_xmppHandlerCollection(self):
        """
        L{subprotocols.XMPPHandlerCollection} is deprecated.
        """
        from wokkel.subprotocols import XMPPHandlerCollection
        XMPPHandlerCollection
        self.lookForDeprecationWarning(
                self.test_xmppHandlerCollection,
                "XMPPHandlerCollection",
                "twisted.words.protocols.jabber.xmlstream."
                    "XMPPHandlerCollection")



class DummyFactory(object):
    """
    Dummy XmlStream factory that only registers bootstrap observers.
    """
    def __init__(self):
        self.callbacks = {}


    def addBootstrap(self, event, callback):
        self.callbacks[event] = callback



class DummyXMPPHandler(subprotocols.XMPPHandler):
    """
    Dummy XMPP subprotocol handler to count the methods are called on it.
    """
    def __init__(self):
        self.doneMade = 0
        self.doneInitialized = 0
        self.doneLost = 0


    def makeConnection(self, xs):
        self.connectionMade()


    def connectionMade(self):
        self.doneMade += 1


    def connectionInitialized(self):
        self.doneInitialized += 1


    def connectionLost(self, reason):
        self.doneLost += 1



class FailureReasonXMPPHandler(subprotocols.XMPPHandler):
    """
    Dummy handler specifically for failure Reason tests.
    """
    def __init__(self):
        self.gotFailureReason = False


    def connectionLost(self, reason):
        if isinstance(reason, failure.Failure):
            self.gotFailureReason = True



class IQGetStanza(generic.Stanza):
    timeout = None

    stanzaKind = 'iq'
    stanzaType = 'get'
    stanzaID = 'test'



class XMPPHandlerTest(unittest.TestCase):
    """
    Tests for L{subprotocols.XMPPHandler}.
    """

    def test_interface(self):
        """
        L{xmlstream.XMPPHandler} implements L{ijabber.IXMPPHandler}.
        """
        verifyObject(ijabber.IXMPPHandler, subprotocols.XMPPHandler())


    def test_send(self):
        """
        Test that data is passed on for sending by the stream manager.
        """
        class DummyStreamManager(object):
            def __init__(self):
                self.outlist = []

            def send(self, data):
                self.outlist.append(data)

        handler = subprotocols.XMPPHandler()
        handler.parent = DummyStreamManager()
        handler.send('<presence/>')
        self.assertEquals(['<presence/>'], handler.parent.outlist)


    def test_makeConnection(self):
        """
        Test that makeConnection saves the XML stream and calls connectionMade.
        """
        class TestXMPPHandler(subprotocols.XMPPHandler):
            def connectionMade(self):
                self.doneMade = True

        handler = TestXMPPHandler()
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        handler.makeConnection(xs)
        self.assertTrue(handler.doneMade)
        self.assertIdentical(xs, handler.xmlstream)


    def test_connectionLost(self):
        """
        Test that connectionLost forgets the XML stream.
        """
        handler = subprotocols.XMPPHandler()
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        handler.makeConnection(xs)
        handler.connectionLost(Exception())
        self.assertIdentical(None, handler.xmlstream)


    def test_request(self):
        """
        A request is passed up to the stream manager.
        """
        class DummyStreamManager(object):
            def __init__(self):
                self.requests = []

            def request(self, request):
                self.requests.append(request)
                return defer.succeed(None)

        handler = subprotocols.XMPPHandler()
        handler.parent = DummyStreamManager()
        request = IQGetStanza()
        d = handler.request(request)
        self.assertEquals(1, len(handler.parent.requests))
        self.assertIdentical(request, handler.parent.requests[-1])
        return d



class StreamManagerTest(unittest.TestCase):
    """
    Tests for L{subprotocols.StreamManager}.
    """

    def setUp(self):
        factory = xmlstream.XmlStreamFactory(xmlstream.Authenticator())
        self.clock = task.Clock()
        self.streamManager = subprotocols.StreamManager(factory, self.clock)
        self.xmlstream = factory.buildProtocol(None)
        self.transport = proto_helpers.StringTransport()
        self.xmlstream.transport = self.transport

        self.request = IQGetStanza()

    def _streamStarted(self):
        """
        Bring the test stream to the initialized state.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
                "<stream:stream xmlns='jabber:client' "
                    "xmlns:stream='http://etherx.jabber.org/streams' "
                    "from='example.com' id='12345'>")
        self.xmlstream.dispatch(self.xmlstream, "//event/stream/authd")


    def test_basic(self):
        """
        Test correct initialization and setup of factory observers.
        """
        factory = DummyFactory()
        sm = subprotocols.StreamManager(factory)
        self.assertIdentical(None, sm.xmlstream)
        self.assertEquals([], sm.handlers)
        self.assertEquals(sm._connected,
                          sm.factory.callbacks['//event/stream/connected'])
        self.assertEquals(sm._authd,
                          sm.factory.callbacks['//event/stream/authd'])
        self.assertEquals(sm._disconnected,
                          sm.factory.callbacks['//event/stream/end'])
        self.assertEquals(sm.initializationFailed,
                          sm.factory.callbacks['//event/xmpp/initfailed'])


    def test_connected(self):
        """
        Test that protocol handlers have their connectionMade method called
        when the XML stream is connected.
        """
        sm = self.streamManager
        handler = DummyXMPPHandler()
        handler.setHandlerParent(sm)
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        sm._connected(xs)
        self.assertEquals(1, handler.doneMade)
        self.assertEquals(0, handler.doneInitialized)
        self.assertEquals(0, handler.doneLost)


    def test_connectedLogTrafficFalse(self):
        """
        Test raw data functions unset when logTraffic is set to False.
        """
        sm = self.streamManager
        handler = DummyXMPPHandler()
        handler.setHandlerParent(sm)
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        sm._connected(xs)
        self.assertIdentical(None, xs.rawDataInFn)
        self.assertIdentical(None, xs.rawDataOutFn)


    def test_connectedLogTrafficTrue(self):
        """
        Test raw data functions set when logTraffic is set to True.
        """
        sm = self.streamManager
        sm.logTraffic = True
        handler = DummyXMPPHandler()
        handler.setHandlerParent(sm)
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        sm._connected(xs)
        self.assertNotIdentical(None, xs.rawDataInFn)
        self.assertNotIdentical(None, xs.rawDataOutFn)


    def test_authd(self):
        """
        Test that protocol handlers have their connectionInitialized method
        called when the XML stream is initialized.
        """
        sm = self.streamManager
        handler = DummyXMPPHandler()
        handler.setHandlerParent(sm)
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        sm._authd(xs)
        self.assertEquals(0, handler.doneMade)
        self.assertEquals(1, handler.doneInitialized)
        self.assertEquals(0, handler.doneLost)


    def test_disconnected(self):
        """
        Protocol handlers have connectionLost called on stream disconnect.
        """
        sm = self.streamManager
        handler = DummyXMPPHandler()
        handler.setHandlerParent(sm)
        sm._disconnected(None)
        self.assertEquals(0, handler.doneMade)
        self.assertEquals(0, handler.doneInitialized)
        self.assertEquals(1, handler.doneLost)


    def test_disconnectedReason(self):
        """
        A L{STREAM_END_EVENT} results in L{StreamManager} firing the handlers
        L{connectionLost} methods, passing a L{failure.Failure} reason.
        """
        sm = self.streamManager
        handler = FailureReasonXMPPHandler()
        handler.setHandlerParent(sm)
        xmlstream.XmlStream(xmlstream.Authenticator())
        sm._disconnected(failure.Failure(Exception("no reason")))
        self.assertEquals(True, handler.gotFailureReason)


    def test_addHandler(self):
        """
        Test the addition of a protocol handler while not connected.
        """
        sm = self.streamManager
        handler = DummyXMPPHandler()
        handler.setHandlerParent(sm)

        self.assertEquals(0, handler.doneMade)
        self.assertEquals(0, handler.doneInitialized)
        self.assertEquals(0, handler.doneLost)


    def test_addHandlerConnected(self):
        """
        Adding a handler when connected doesn't call connectionInitialized.
        """
        sm = self.streamManager
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        sm._connected(xs)
        handler = DummyXMPPHandler()
        handler.setHandlerParent(sm)

        self.assertEquals(1, handler.doneMade)
        self.assertEquals(0, handler.doneInitialized)
        self.assertEquals(0, handler.doneLost)


    def test_addHandlerConnectedNested(self):
        """
        Adding a handler in connectionMade doesn't cause 2nd call.
        """
        class NestingHandler(DummyXMPPHandler):
            nestedHandler = None

            def connectionMade(self):
                DummyXMPPHandler.connectionMade(self)
                self.nestedHandler = DummyXMPPHandler()
                self.nestedHandler.setHandlerParent(self.parent)

        sm = self.streamManager
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        handler = NestingHandler()
        handler.setHandlerParent(sm)
        sm._connected(xs)

        self.assertEquals(1, handler.doneMade)
        self.assertEquals(0, handler.doneInitialized)
        self.assertEquals(0, handler.doneLost)

        self.assertEquals(1, handler.nestedHandler.doneMade)
        self.assertEquals(0, handler.nestedHandler.doneInitialized)
        self.assertEquals(0, handler.nestedHandler.doneLost)



    def test_addHandlerInitialized(self):
        """
        Test the addition of a protocol handler after the stream
        have been initialized.

        Make sure that the handler will have the connected stream
        passed via C{makeConnection} and have C{connectionInitialized}
        called.
        """
        sm = self.streamManager
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        sm._connected(xs)
        sm._authd(xs)
        handler = DummyXMPPHandler()
        handler.setHandlerParent(sm)

        self.assertEquals(1, handler.doneMade)
        self.assertEquals(1, handler.doneInitialized)
        self.assertEquals(0, handler.doneLost)


    def test_addHandlerInitializedNested(self):
        """
        Adding a handler in connectionInitialized doesn't cause 2nd call.
        """
        class NestingHandler(DummyXMPPHandler):
            nestedHandler = None

            def connectionInitialized(self):
                DummyXMPPHandler.connectionInitialized(self)
                self.nestedHandler = DummyXMPPHandler()
                self.nestedHandler.setHandlerParent(self.parent)

        sm = self.streamManager
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        handler = NestingHandler()
        handler.setHandlerParent(sm)
        sm._connected(xs)
        sm._authd(xs)

        self.assertEquals(1, handler.doneMade)
        self.assertEquals(1, handler.doneInitialized)
        self.assertEquals(0, handler.doneLost)

        self.assertEquals(1, handler.nestedHandler.doneMade)
        self.assertEquals(1, handler.nestedHandler.doneInitialized)
        self.assertEquals(0, handler.nestedHandler.doneLost)


    def test_addHandlerConnectionLostNested(self):
        """
        Adding a handler in connectionLost doesn't call connectionLost there.
        """
        class NestingHandler(DummyXMPPHandler):
            nestedHandler = None

            def connectionLost(self, reason):
                DummyXMPPHandler.connectionLost(self, reason)
                self.nestedHandler = DummyXMPPHandler()
                self.nestedHandler.setHandlerParent(self.parent)

        sm = self.streamManager
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        handler = NestingHandler()
        handler.setHandlerParent(sm)
        sm._connected(xs)
        sm._authd(xs)
        sm._disconnected(xs)

        self.assertEquals(1, handler.doneMade)
        self.assertEquals(1, handler.doneInitialized)
        self.assertEquals(1, handler.doneLost)

        self.assertEquals(0, handler.nestedHandler.doneMade)
        self.assertEquals(0, handler.nestedHandler.doneInitialized)
        self.assertEquals(0, handler.nestedHandler.doneLost)



    def test_removeHandler(self):
        """
        Test removal of protocol handler.
        """
        sm = self.streamManager
        handler = DummyXMPPHandler()
        handler.setHandlerParent(sm)
        handler.disownHandlerParent(sm)
        self.assertNotIn(handler, sm)
        self.assertIdentical(None, handler.parent)


    def test_sendInitialized(self):
        """
        Test send when the stream has been initialized.

        The data should be sent directly over the XML stream.
        """
        factory = xmlstream.XmlStreamFactory(xmlstream.Authenticator())
        sm = subprotocols.StreamManager(factory)
        xs = factory.buildProtocol(None)
        xs.transport = proto_helpers.StringTransport()
        xs.connectionMade()
        xs.dataReceived("<stream:stream xmlns='jabber:client' "
                        "xmlns:stream='http://etherx.jabber.org/streams' "
                        "from='example.com' id='12345'>")
        xs.dispatch(xs, "//event/stream/authd")
        sm.send("<presence/>")
        self.assertEquals("<presence/>", xs.transport.value())


    def test_sendNotConnected(self):
        """
        Test send when there is no established XML stream.

        The data should be cached until an XML stream has been established and
        initialized.
        """
        factory = xmlstream.XmlStreamFactory(xmlstream.Authenticator())
        sm = subprotocols.StreamManager(factory)
        handler = DummyXMPPHandler()
        sm.addHandler(handler)

        xs = factory.buildProtocol(None)
        xs.transport = proto_helpers.StringTransport()
        sm.send("<presence/>")
        self.assertEquals("", xs.transport.value())
        self.assertEquals("<presence/>", sm._packetQueue[0])

        xs.connectionMade()
        self.assertEquals("", xs.transport.value())
        self.assertEquals("<presence/>", sm._packetQueue[0])

        xs.dataReceived("<stream:stream xmlns='jabber:client' "
                        "xmlns:stream='http://etherx.jabber.org/streams' "
                        "from='example.com' id='12345'>")
        xs.dispatch(xs, "//event/stream/authd")

        self.assertEquals("<presence/>", xs.transport.value())
        self.assertFalse(sm._packetQueue)


    def test_sendNotInitialized(self):
        """
        Test send when the stream is connected but not yet initialized.

        The data should be cached until the XML stream has been initialized.
        """
        factory = xmlstream.XmlStreamFactory(xmlstream.Authenticator())
        sm = subprotocols.StreamManager(factory)
        xs = factory.buildProtocol(None)
        xs.transport = proto_helpers.StringTransport()
        xs.connectionMade()
        xs.dataReceived("<stream:stream xmlns='jabber:client' "
                        "xmlns:stream='http://etherx.jabber.org/streams' "
                        "from='example.com' id='12345'>")
        sm.send("<presence/>")
        self.assertEquals("", xs.transport.value())
        self.assertEquals("<presence/>", sm._packetQueue[0])


    def test_sendDisconnected(self):
        """
        Test send after XML stream disconnection.

        The data should be cached until a new XML stream has been established
        and initialized.
        """
        factory = xmlstream.XmlStreamFactory(xmlstream.Authenticator())
        sm = subprotocols.StreamManager(factory)
        handler = DummyXMPPHandler()
        sm.addHandler(handler)

        xs = factory.buildProtocol(None)
        xs.connectionMade()
        xs.transport = proto_helpers.StringTransport()
        xs.connectionLost(None)

        sm.send("<presence/>")
        self.assertEquals("", xs.transport.value())
        self.assertEquals("<presence/>", sm._packetQueue[0])


    def test_requestSendInitialized(self):
        """
        A request is sent out over the wire when the stream is initialized.
        """
        self._streamStarted()

        self.streamManager.request(self.request)
        expected = u"<iq type='get' id='%s'/>" % self.request.stanzaID
        self.assertEquals(expected, self.transport.value())


    def test_requestSendInitializedFreshID(self):
        """
        A request without an ID gets a fresh one upon send.
        """
        self._streamStarted()

        self.request.stanzaID = None
        self.streamManager.request(self.request)
        self.assertNotIdentical(None, self.request.stanzaID)
        expected = u"<iq type='get' id='%s'/>" % self.request.stanzaID
        self.assertEquals(expected, self.transport.value())


    def test_requestSendNotConnected(self):
        """
        A request is queued until a stream is initialized.
        """
        handler = DummyXMPPHandler()
        self.streamManager.addHandler(handler)

        self.streamManager.request(self.request)
        expected = u"<iq type='get' id='test'/>"

        xs = self.xmlstream
        self.assertEquals("", xs.transport.value())

        xs.connectionMade()
        self.assertEquals("", xs.transport.value())

        xs.dataReceived("<stream:stream xmlns='jabber:client' "
                        "xmlns:stream='http://etherx.jabber.org/streams' "
                        "from='example.com' id='12345'>")
        xs.dispatch(xs, "//event/stream/authd")

        self.assertEquals(expected, xs.transport.value())
        self.assertFalse(self.streamManager._packetQueue)


    def test_requestResultResponse(self):
        """
        A result response gets the request deferred fired with the response.
        """
        def cb(result):
            self.assertEquals(result['type'], 'result')

        self._streamStarted()
        d = self.streamManager.request(self.request)
        d.addCallback(cb)

        xs = self.xmlstream
        xs.dataReceived("<iq type='result' id='test'/>")
        return d


    def test_requestErrorResponse(self):
        """
        An error response gets the request deferred fired with a failure.
        """
        self._streamStarted()
        d = self.streamManager.request(self.request)
        self.assertFailure(d, error.StanzaError)

        xs = self.xmlstream
        xs.dataReceived("<iq type='error' id='test'/>")
        return d


    def test_requestNonTrackedResponse(self):
        """
        Test that untracked iq responses don't trigger any action.

        Untracked means that the id of the incoming response iq is not
        in the stream's C{iqDeferreds} dictionary.
        """
        # Set up a fallback handler that checks the stanza's handled attribute.
        # If that is set to True, the iq tracker claims to have handled the
        # response.
        dispatched = []
        def cb(iq):
            dispatched.append(iq)

        self._streamStarted()
        self.xmlstream.addObserver("/iq", cb, -1)

        # Receive an untracked iq response
        self.xmlstream.dataReceived("<iq type='result' id='other'/>")
        self.assertEquals(1, len(dispatched))
        self.assertFalse(getattr(dispatched[-1], 'handled', False))


    def test_requestCleanup(self):
        """
        Test if the deferred associated with an iq request is removed
        from the list kept in the L{XmlStream} object after it has
        been fired.
        """
        self._streamStarted()
        d = self.streamManager.request(self.request)
        xs = self.xmlstream
        xs.dataReceived("<iq type='result' id='test'/>")
        self.assertNotIn('test', self.streamManager._iqDeferreds)
        return d


    def test_requestDisconnectCleanup(self):
        """
        Test if deferreds for iq's that haven't yet received a response
        have their errback called on stream disconnect.
        """
        d = self.streamManager.request(self.request)
        xs = self.xmlstream
        xs.connectionLost(failure.Failure(ConnectionDone()))
        self.assertFailure(d, ConnectionDone)
        return d


    def test_requestNoModifyingDict(self):
        """
        Test to make sure the errbacks cannot cause the iteration of the
        iqDeferreds to blow up in our face.
        """

        def eb(failure):
            d = xmlstream.IQ(self.xmlstream).send()
            d.addErrback(eb)

        d = self.streamManager.request(self.request)
        d.addErrback(eb)
        self.xmlstream.connectionLost(failure.Failure(ConnectionDone()))
        return d


    def test_requestTimingOut(self):
        """
        Test that an iq request with a defined timeout times out.
        """
        self.request.timeout = 60
        d = self.streamManager.request(self.request)
        self.assertFailure(d, xmlstream.TimeoutError)

        self.clock.pump([1, 60])
        self.assertFalse(self.clock.calls)
        self.assertFalse(self.streamManager._iqDeferreds)
        return d


    def test_requestNotTimingOut(self):
        """
        Test that an iq request with a defined timeout does not time out
        when a response was received before the timeout period elapsed.
        """
        self._streamStarted()
        self.request.timeout = 60
        d = self.streamManager.request(self.request)
        self.clock.callLater(1, self.xmlstream.dataReceived,
                             "<iq type='result' id='test'/>")
        self.clock.pump([1, 1])
        self.assertFalse(self.clock.calls)
        return d


    def test_requestDisconnectTimeoutCancellation(self):
        """
        Test if timeouts for iq's that haven't yet received a response
        are cancelled on stream disconnect.
        """

        self.request.timeout = 60
        d = self.streamManager.request(self.request)

        self.xmlstream.connectionLost(failure.Failure(ConnectionDone()))
        self.assertFailure(d, ConnectionDone)
        self.assertFalse(self.clock.calls)
        return d


    def test_requestNotIQ(self):
        """
        The request stanza must be an iq.
        """
        stanza = generic.Stanza()
        stanza.stanzaKind = 'message'

        d = self.streamManager.request(stanza)
        self.assertFailure(d, ValueError)


    def test_requestNotResult(self):
        """
        The request stanza cannot be of type 'result'.
        """
        stanza = generic.Stanza()
        stanza.stanzaKind = 'iq'
        stanza.stanzaType = 'result'

        d = self.streamManager.request(stanza)
        self.assertFailure(d, ValueError)


    def test_requestNotError(self):
        """
        The request stanza cannot be of type 'error'.
        """
        stanza = generic.Stanza()
        stanza.stanzaKind = 'iq'
        stanza.stanzaType = 'error'

        d = self.streamManager.request(stanza)
        self.assertFailure(d, ValueError)



class DummyIQHandler(subprotocols.IQHandlerMixin):
    iqHandlers = {'/iq[@type="get"]': 'onGet'}

    def __init__(self):
        self.output = []
        self.xmlstream = xmlstream.XmlStream(xmlstream.Authenticator())
        self.xmlstream.send = self.output.append

    def send(self, obj):
        self.xmlstream.send(obj)


class IQHandlerTest(unittest.TestCase):

    def test_match(self):
        """
        Test that the matching handler gets called.
        """

        class Handler(DummyIQHandler):
            called = False

            def onGet(self, iq):
                self.called = True

        iq = domish.Element((None, 'iq'))
        iq['type'] = 'get'
        iq['id'] = 'r1'
        handler = Handler()
        handler.handleRequest(iq)
        self.assertTrue(handler.called)

    def test_noMatch(self):
        """
        Test that the matching handler gets called.
        """

        class Handler(DummyIQHandler):
            called = False

            def onGet(self, iq):
                self.called = True

        iq = domish.Element((None, 'iq'))
        iq['type'] = 'set'
        iq['id'] = 'r1'
        handler = Handler()
        handler.handleRequest(iq)
        self.assertFalse(handler.called)

    def test_success(self):
        """
        Test response when the request is handled successfully.
        """

        class Handler(DummyIQHandler):
            def onGet(self, iq):
                return None

        iq = domish.Element((None, 'iq'))
        iq['type'] = 'get'
        iq['id'] = 'r1'
        handler = Handler()
        handler.handleRequest(iq)
        response = handler.output[-1]
        self.assertEquals(None, response.uri)
        self.assertEquals('iq', response.name)
        self.assertEquals('result', response['type'])

    def test_successPayload(self):
        """
        Test response when the request is handled successfully with payload.
        """

        class Handler(DummyIQHandler):
            payload = domish.Element(('testns', 'foo'))

            def onGet(self, iq):
                return self.payload

        iq = domish.Element((None, 'iq'))
        iq['type'] = 'get'
        iq['id'] = 'r1'
        handler = Handler()
        handler.handleRequest(iq)
        response = handler.output[-1]
        self.assertEquals(None, response.uri)
        self.assertEquals('iq', response.name)
        self.assertEquals('result', response['type'])
        payload = response.elements().next()
        self.assertEqual(handler.payload, payload)

    def test_successDeferred(self):
        """
        Test response when where the handler was a deferred.
        """

        class Handler(DummyIQHandler):
            def onGet(self, iq):
                return defer.succeed(None)

        iq = domish.Element((None, 'iq'))
        iq['type'] = 'get'
        iq['id'] = 'r1'
        handler = Handler()
        handler.handleRequest(iq)
        response = handler.output[-1]
        self.assertEquals(None, response.uri)
        self.assertEquals('iq', response.name)
        self.assertEquals('result', response['type'])

    def test_failure(self):
        """
        Test response when the request is handled unsuccessfully.
        """

        class Handler(DummyIQHandler):
            def onGet(self, iq):
                raise error.StanzaError('forbidden')

        iq = domish.Element((None, 'iq'))
        iq['type'] = 'get'
        iq['id'] = 'r1'
        handler = Handler()
        handler.handleRequest(iq)
        response = handler.output[-1]
        self.assertEquals(None, response.uri)
        self.assertEquals('iq', response.name)
        self.assertEquals('error', response['type'])
        e = error.exceptionFromStanza(response)
        self.assertEquals('forbidden', e.condition)

    def test_failureUnknown(self):
        """
        Test response when the request handler raises a non-stanza-error.
        """

        class TestError(Exception):
            pass

        class Handler(DummyIQHandler):
            def onGet(self, iq):
                raise TestError()

        iq = domish.Element((None, 'iq'))
        iq['type'] = 'get'
        iq['id'] = 'r1'
        handler = Handler()
        handler.handleRequest(iq)
        response = handler.output[-1]
        self.assertEquals(None, response.uri)
        self.assertEquals('iq', response.name)
        self.assertEquals('error', response['type'])
        e = error.exceptionFromStanza(response)
        self.assertEquals('internal-server-error', e.condition)
        self.assertEquals(1, len(self.flushLoggedErrors(TestError)))

    def test_notImplemented(self):
        """
        Test response when the request is recognised but not implemented.
        """

        class Handler(DummyIQHandler):
            def onGet(self, iq):
                raise NotImplementedError()

        iq = domish.Element((None, 'iq'))
        iq['type'] = 'get'
        iq['id'] = 'r1'
        handler = Handler()
        handler.handleRequest(iq)
        response = handler.output[-1]
        self.assertEquals(None, response.uri)
        self.assertEquals('iq', response.name)
        self.assertEquals('error', response['type'])
        e = error.exceptionFromStanza(response)
        self.assertEquals('feature-not-implemented', e.condition)

    def test_noHandler(self):
        """
        Test when the request is not recognised.
        """

        iq = domish.Element((None, 'iq'))
        iq['type'] = 'set'
        iq['id'] = 'r1'
        handler = DummyIQHandler()
        handler.handleRequest(iq)
        response = handler.output[-1]
        self.assertEquals(None, response.uri)
        self.assertEquals('iq', response.name)
        self.assertEquals('error', response['type'])
        e = error.exceptionFromStanza(response)
        self.assertEquals('feature-not-implemented', e.condition)
