# Copyright (c) 2003-2007 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.subprotocols}
"""

from twisted.trial import unittest
from twisted.test import proto_helpers
from twisted.internet import defer
from twisted.words.xish import domish
from twisted.words.protocols.jabber import error, xmlstream

from wokkel import subprotocols

class DummyFactory(object):
    def __init__(self):
        self.callbacks = {}

    def addBootstrap(self, event, callback):
        self.callbacks[event] = callback


class DummyXMPPHandler(subprotocols.XMPPHandler):
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


class XMPPHandlerTest(unittest.TestCase):

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


class StreamManagerTest(unittest.TestCase):

    def setUp(self):
        factory = DummyFactory()
        self.streamManager = subprotocols.StreamManager(factory)

    def test_basic(self):
        """
        Test correct initialization and setup of factory observers.
        """
        sm = self.streamManager
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

    def test__connected(self):
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

    def test__authd(self):
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

    def test__disconnected(self):
        """
        Test that protocol handlers have their connectionLost method
        called when the XML stream is disconnected.
        """
        sm = self.streamManager
        handler = DummyXMPPHandler()
        handler.setHandlerParent(sm)
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        sm._disconnected(xs)
        self.assertEquals(0, handler.doneMade)
        self.assertEquals(0, handler.doneInitialized)
        self.assertEquals(1, handler.doneLost)

    def test_addHandler(self):
        """
        Test the addition of a protocol handler while not connected.
        """
        sm = self.streamManager
        handler = DummyXMPPHandler()
        handler.setHandlerParent(sm)
        self.assertIn(handler, sm)
        self.assertIdentical(sm, handler.parent)

        self.assertEquals(0, handler.doneMade)
        self.assertEquals(0, handler.doneInitialized)
        self.assertEquals(0, handler.doneLost)

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
        self.failIf(sm._packetQueue)

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
