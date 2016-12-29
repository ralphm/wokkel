# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.component}.
"""

from __future__ import division, absolute_import

from zope.interface.verify import verifyObject

from twisted.internet.base import BaseConnector
from twisted.internet.error import ConnectionRefusedError
from twisted.internet.task import Clock
from twisted.python import failure
from twisted.trial import unittest
from twisted.words.protocols.jabber import xmlstream
from twisted.words.protocols.jabber.ijabber import IXMPPHandlerCollection
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import XMPPHandler
from twisted.words.xish import domish

from wokkel import component
from wokkel.generic import XmlPipe

class FakeConnector(BaseConnector):
    """
    Fake connector that counts connection attempts.
    """
    connects = 0

    def connect(self):
        self.connects += 1
        BaseConnector.connect(self)


    def _makeTransport(self):
        return None



class TestableComponent(component.Component):
    """
    Testable component.

    This component provides the created factory with a L{Clock}
    instead of the regular reactor and uses L{FakeConnector} for testing
    connects and reconnects.
    """

    def __init__(self, *args, **kwargs):
        component.Component.__init__(self, *args, **kwargs)
        self.factory.clock = Clock()


    def _getConnection(self):
        c = FakeConnector(self.factory, None, None)
        c.connect()
        return c



class ComponentTest(unittest.TestCase):
    """
    Tests for L{component.Component}.
    """
    def test_startServiceReconnectAfterFailure(self):
        """
        When the first connection attempt fails, retry.
        """
        comp = TestableComponent('example.org', 5347,
                                 'test.example.org', 'secret')

        # Starting the service initiates a connection attempt.
        comp.startService()
        connector = comp._connection
        self.assertEqual(1, connector.connects)

        # Fail the connection.
        connector.connectionFailed(ConnectionRefusedError())

        # After a back-off delay, a new connection is attempted.
        comp.factory.clock.advance(5)
        self.assertEqual(2, connector.connects)


    def test_stopServiceNoReconnect(self):
        """
        When the service is stopped, no reconnect is attempted.
        """
        comp = TestableComponent('example.org', 5347,
                                 'test.example.org', 'secret')

        # Starting the service initiates a connection attempt.
        comp.startService()
        connector = comp._connection

        # Fail the connection.
        connector.connectionFailed(ConnectionRefusedError())

        # If the service is stopped before the back-off delay expires,
        # no new connection is attempted.
        comp.factory.clock.advance(1)
        comp.stopService()
        comp.factory.clock.advance(4)
        self.assertEqual(1, connector.connects)



class InternalComponentTest(unittest.TestCase):
    """
    Tests for L{component.InternalComponent}.
    """

    def setUp(self):
        self.router = component.Router()
        self.component = component.InternalComponent(self.router, 'component')


    def test_interface(self):
        """
        L{component.InternalComponent} implements
        L{IXMPPHandlerCollection}.
        """
        verifyObject(IXMPPHandlerCollection, self.component)


    def test_startServiceRunning(self):
        """
        Starting the service makes it running.
        """
        self.assertFalse(self.component.running)
        self.component.startService()
        self.assertTrue(self.component.running)


    def test_startServiceAddRoute(self):
        """
        Starting the service creates a new route.
        """
        self.component.startService()
        self.assertIn('component', self.router.routes)


    def test_startServiceNoDomain(self):
        self.component = component.InternalComponent(self.router)
        self.component.startService()


    def test_startServiceAddMultipleRoutes(self):
        """
        Starting the service creates a new route.
        """
        self.component.domains.add('component2')
        self.component.startService()
        self.assertIn('component', self.router.routes)
        self.assertIn('component2', self.router.routes)


    def test_startServiceHandlerDispatch(self):
        """
        Starting the service hooks up handlers.
        """
        events = []

        class TestHandler(XMPPHandler):

            def connectionInitialized(self):
                fn = lambda obj: events.append(obj)
                self.xmlstream.addObserver('//event/test', fn)

        TestHandler().setHandlerParent(self.component)

        self.component.startService()
        self.assertEquals([], events)
        self.component.xmlstream.dispatch(None, '//event/test')
        self.assertEquals([None], events)


    def test_stopServiceNotRunning(self):
        """
        Stopping the service makes it not running.
        """
        self.component.startService()
        self.component.stopService()
        self.assertFalse(self.component.running)


    def test_stopServiceRemoveRoute(self):
        """
        Stopping the service removes routes.
        """
        self.component.startService()
        self.component.stopService()
        self.assertNotIn('component', self.router.routes)


    def test_stopServiceNoDomain(self):
        self.component = component.InternalComponent(self.router)
        self.component.startService()
        self.component.stopService()


    def test_startServiceRemoveMultipleRoutes(self):
        """
        Starting the service creates a new route.
        """
        self.component.domains.add('component2')
        self.component.startService()
        self.component.stopService()
        self.assertNotIn('component', self.router.routes)
        self.assertNotIn('component2', self.router.routes)


    def test_stopServiceHandlerDispatch(self):
        """
        Stopping the service disconnects handlers.
        """
        events = []

        class TestHandler(XMPPHandler):

            def connectionLost(self, reason):
                events.append(reason)

        TestHandler().setHandlerParent(self.component)

        self.component.startService()
        self.component.stopService()
        self.assertEquals(1, len(events))


    def test_addHandler(self):
        """
        Adding a handler connects it to the stream.
        """
        events = []

        class TestHandler(XMPPHandler):

            def connectionInitialized(self):
                fn = lambda obj: events.append(obj)
                self.xmlstream.addObserver('//event/test', fn)

        self.component.startService()
        self.component.xmlstream.dispatch(None, '//event/test')
        self.assertEquals([], events)

        TestHandler().setHandlerParent(self.component)
        self.component.xmlstream.dispatch(None, '//event/test')
        self.assertEquals([None], events)


    def test_send(self):
        """
        A message sent from the component ends up at the router.
        """
        events = []
        fn = lambda obj: events.append(obj)
        message = domish.Element((None, 'message'))

        self.router.route = fn
        self.component.startService()
        self.component.send(message)

        self.assertEquals([message], events)



class RouterTest(unittest.TestCase):
    """
    Tests for L{component.Router}.
    """

    def test_addRoute(self):
        """
        Test route registration and routing on incoming stanzas.
        """
        router = component.Router()
        routed = []
        router.route = lambda element: routed.append(element)

        pipe = XmlPipe()
        router.addRoute('example.org', pipe.sink)
        self.assertEquals(1, len(router.routes))
        self.assertEquals(pipe.sink, router.routes['example.org'])

        element = domish.Element(('testns', 'test'))
        pipe.source.send(element)
        self.assertEquals([element], routed)


    def test_route(self):
        """
        Test routing of a message.
        """
        component1 = XmlPipe()
        component2 = XmlPipe()
        router = component.Router()
        router.addRoute('component1.example.org', component1.sink)
        router.addRoute('component2.example.org', component2.sink)

        outgoing = []
        component2.source.addObserver('/*',
                                      lambda element: outgoing.append(element))
        stanza = domish.Element((None, 'presence'))
        stanza['from'] = 'component1.example.org'
        stanza['to'] = 'component2.example.org'
        component1.source.send(stanza)
        self.assertEquals([stanza], outgoing)


    def test_routeDefault(self):
        """
        Test routing of a message using the default route.

        The default route is the one with L{None} as its key in the
        routing table. It is taken when there is no more specific route
        in the routing table that matches the stanza's destination.
        """
        component1 = XmlPipe()
        s2s = XmlPipe()
        router = component.Router()
        router.addRoute('component1.example.org', component1.sink)
        router.addRoute(None, s2s.sink)

        outgoing = []
        s2s.source.addObserver('/*', lambda element: outgoing.append(element))
        stanza = domish.Element((None, 'presence'))
        stanza['from'] = 'component1.example.org'
        stanza['to'] = 'example.com'
        component1.source.send(stanza)
        self.assertEquals([stanza], outgoing)



class ListenComponentAuthenticatorTest(unittest.TestCase):
    """
    Tests for L{component.ListenComponentAuthenticator}.
    """

    def setUp(self):
        self.output = []
        authenticator = component.ListenComponentAuthenticator('secret')
        self.xmlstream = xmlstream.XmlStream(authenticator)
        self.xmlstream.send = self.output.append


    def loseConnection(self):
        """
        Stub loseConnection because we are a transport.
        """
        self.xmlstream.connectionLost("no reason")


    def test_streamStarted(self):
        """
        The received stream header should set several attributes.
        """
        observers = []

        def addOnetimeObserver(event, observerfn):
            observers.append((event, observerfn))

        xs = self.xmlstream
        xs.addOnetimeObserver = addOnetimeObserver

        xs.makeConnection(self)
        self.assertIdentical(None, xs.sid)
        self.assertFalse(xs._headerSent)

        xs.dataReceived("<stream:stream xmlns='jabber:component:accept' "
                         "xmlns:stream='http://etherx.jabber.org/streams' "
                         "to='component.example.org'>")
        self.assertEqual((0, 0), xs.version)
        self.assertNotIdentical(None, xs.sid)
        self.assertTrue(xs._headerSent)
        self.assertEquals(('/*', xs.authenticator.onElement), observers[-1])


    def test_streamStartedWrongNamespace(self):
        """
        The received stream header should have a correct namespace.
        """
        streamErrors = []

        xs = self.xmlstream
        xs.sendStreamError = streamErrors.append
        xs.makeConnection(self)
        xs.dataReceived("<stream:stream xmlns='jabber:client' "
                         "xmlns:stream='http://etherx.jabber.org/streams' "
                         "to='component.example.org'>")
        self.assertEquals(1, len(streamErrors))
        self.assertEquals('invalid-namespace', streamErrors[-1].condition)


    def test_streamStartedNoTo(self):
        """
        The received stream header should have a 'to' attribute.
        """
        streamErrors = []

        xs = self.xmlstream
        xs.sendStreamError = streamErrors.append
        xs.makeConnection(self)
        xs.dataReceived("<stream:stream xmlns='jabber:component:accept' "
                         "xmlns:stream='http://etherx.jabber.org/streams'>")
        self.assertEquals(1, len(streamErrors))
        self.assertEquals('improper-addressing', streamErrors[-1].condition)


    def test_onElement(self):
        """
        We expect a handshake element with a hash.
        """
        handshakes = []

        xs = self.xmlstream
        xs.authenticator.onHandshake = handshakes.append

        handshake = domish.Element(('jabber:component:accept', 'handshake'))
        handshake.addContent('1234')
        xs.authenticator.onElement(handshake)
        self.assertEqual('1234', handshakes[-1])

    def test_onElementNotHandshake(self):
        """
        Reject elements that are not handshakes
        """
        handshakes = []
        streamErrors = []

        xs = self.xmlstream
        xs.authenticator.onHandshake = handshakes.append
        xs.sendStreamError = streamErrors.append

        element = domish.Element(('jabber:component:accept', 'message'))
        xs.authenticator.onElement(element)
        self.assertFalse(handshakes)
        self.assertEquals('not-authorized', streamErrors[-1].condition)


    def test_onHandshake(self):
        """
        Receiving a handshake matching the secret authenticates the stream.
        """
        authd = []

        def authenticated(xs):
            authd.append(xs)

        xs = self.xmlstream
        xs.addOnetimeObserver(xmlstream.STREAM_AUTHD_EVENT, authenticated)
        xs.sid = u'1234'
        theHash = '32532c0f7dbf1253c095b18b18e36d38d94c1256'
        xs.authenticator.onHandshake(theHash)
        self.assertEqual('<handshake/>', self.output[-1])
        self.assertEquals(1, len(authd))


    def test_onHandshakeWrongHash(self):
        """
        Receiving a bad handshake should yield a stream error.
        """
        streamErrors = []
        authd = []

        def authenticated(xs):
            authd.append(xs)

        xs = self.xmlstream
        xs.addOnetimeObserver(xmlstream.STREAM_AUTHD_EVENT, authenticated)
        xs.sendStreamError = streamErrors.append

        xs.sid = u'1234'
        theHash = '1234'
        xs.authenticator.onHandshake(theHash)
        self.assertEquals('not-authorized', streamErrors[-1].condition)
        self.assertEquals(0, len(authd))



class XMPPComponentServerFactoryTest(unittest.TestCase):
    """
    Tests for L{component.XMPPComponentServerFactory}.
    """

    def setUp(self):
        self.router = component.Router()
        self.factory = component.XMPPComponentServerFactory(self.router,
                                                            'secret')
        self.xmlstream = self.factory.buildProtocol(None)
        self.xmlstream.thisEntity = JID('component.example.org')


    def test_makeConnection(self):
        """
        A new connection increases the stream serial count. No logs by default.
        """
        self.xmlstream.dispatch(self.xmlstream,
                                xmlstream.STREAM_CONNECTED_EVENT)
        self.assertEqual(0, self.xmlstream.serial)
        self.assertEqual(1, self.factory.serial)
        self.assertIdentical(None, self.xmlstream.rawDataInFn)
        self.assertIdentical(None, self.xmlstream.rawDataOutFn)


    def test_makeConnectionLogTraffic(self):
        """
        Setting logTraffic should set up raw data loggers.
        """
        self.factory.logTraffic = True
        self.xmlstream.dispatch(self.xmlstream,
                                xmlstream.STREAM_CONNECTED_EVENT)
        self.assertNotIdentical(None, self.xmlstream.rawDataInFn)
        self.assertNotIdentical(None, self.xmlstream.rawDataOutFn)


    def test_onError(self):
        """
        An observer for stream errors should trigger onError to log it.
        """
        self.xmlstream.dispatch(self.xmlstream,
                                xmlstream.STREAM_CONNECTED_EVENT)

        class TestError(Exception):
            pass

        reason = failure.Failure(TestError())
        self.xmlstream.dispatch(reason, xmlstream.STREAM_ERROR_EVENT)
        self.assertEqual(1, len(self.flushLoggedErrors(TestError)))


    def test_connectionInitialized(self):
        """
        Make sure a new stream is added to the routing table.
        """
        self.xmlstream.dispatch(self.xmlstream, xmlstream.STREAM_AUTHD_EVENT)
        self.assertIn('component.example.org', self.router.routes)
        self.assertIdentical(self.xmlstream,
                             self.router.routes['component.example.org'])


    def test_connectionLost(self):
        """
        Make sure a stream is removed from the routing table on disconnect.
        """
        self.xmlstream.dispatch(self.xmlstream, xmlstream.STREAM_AUTHD_EVENT)
        self.xmlstream.dispatch(None, xmlstream.STREAM_END_EVENT)
        self.assertNotIn('component.example.org', self.router.routes)
