# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.server}.
"""

from twisted.internet import defer
from twisted.python import failure
from twisted.test.proto_helpers import StringTransport
from twisted.trial import unittest
from twisted.words.protocols.jabber import error, jid, xmlstream
from twisted.words.xish import domish

from wokkel import component, server

NS_STREAMS = 'http://etherx.jabber.org/streams'
NS_DIALBACK = "jabber:server:dialback"

class GenerateKeyTest(unittest.TestCase):
    """
    Tests for L{server.generateKey}.
    """

    def testBasic(self):
        originating = "example.org"
        receiving = "xmpp.example.com"
        sid = "D60000229F"
        secret = "s3cr3tf0rd14lb4ck"

        key = server.generateKey(secret, receiving, originating, sid)

        self.assertEqual(key,
            '37c69b1cf07a3f67c04a5ef5902fa5114f2c76fe4a2686482ba5b89323075643')



class XMPPServerListenAuthenticatorTest(unittest.TestCase):
    """
    Tests for L{server.XMPPServerListenAuthenticator}.
    """

    secret = "s3cr3tf0rd14lb4ck"
    originating = "example.org"
    receiving = "xmpp.example.com"
    sid = "D60000229F"
    key = '37c69b1cf07a3f67c04a5ef5902fa5114f2c76fe4a2686482ba5b89323075643'

    def setUp(self):
        self.output = []

        class MyService(object):
            pass

        self.service = MyService()
        self.service.defaultDomain = self.receiving
        self.service.domains = [self.receiving, 'pubsub.'+self.receiving]
        self.service.secret = self.secret

        self.authenticator = server.XMPPServerListenAuthenticator(self.service)
        self.xmlstream = xmlstream.XmlStream(self.authenticator)
        self.xmlstream.send = self.output.append
        self.xmlstream.transport = StringTransport()


    def test_attributes(self):
        """
        Test attributes of authenticator and stream objects.
        """
        self.assertEqual(self.service, self.authenticator.service)
        self.assertEqual(self.xmlstream.initiating, False)


    def test_streamStartedVersion0(self):
        """
        The authenticator supports pre-XMPP 1.0 streams.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='jabber:server' "
                           "to='xmpp.example.com'>")
        self.assertEqual((0, 0), self.xmlstream.version)


    def test_streamStartedVersion1(self):
        """
        The authenticator supports XMPP 1.0 streams.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='jabber:server' "
                           "to='xmpp.example.com' "
                           "version='1.0'>")
        self.assertEqual((1, 0), self.xmlstream.version)


    def test_streamStartedSID(self):
        """
        The response stream will have a stream ID.
        """
        self.xmlstream.connectionMade()
        self.assertIdentical(None, self.xmlstream.sid)

        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='jabber:server' "
                           "to='xmpp.example.com' "
                           "version='1.0'>")
        self.assertNotIdentical(None, self.xmlstream.sid)


    def test_streamStartedSentResponseHeader(self):
        """
        A stream header is sent in response to the incoming stream header.
        """
        self.xmlstream.connectionMade()
        self.assertFalse(self.xmlstream._headerSent)

        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='jabber:server' "
                           "to='xmpp.example.com'>")
        self.assertTrue(self.xmlstream._headerSent)


    def test_streamStartedNotSentFeatures(self):
        """
        No features are sent in response to an XMPP < 1.0 stream header.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='jabber:server' "
                           "to='xmpp.example.com'>")
        self.assertEqual(1, len(self.output))


    def test_streamStartedSentFeatures(self):
        """
        Features are sent in response to an XMPP >= 1.0 stream header.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='jabber:server' "
                           "to='xmpp.example.com' "
                           "version='1.0'>")
        self.assertEqual(2, len(self.output))
        features = self.output[-1]
        self.assertEqual(NS_STREAMS, features.uri)
        self.assertEqual('features', features.name)


    def test_streamRootElement(self):
        """
        Test stream error on wrong stream namespace.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='badns' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='jabber:server' "
                           "to='xmpp.example.com'>")

        self.assertEqual(3, len(self.output))
        exc = error.exceptionFromStreamError(self.output[1])
        self.assertEqual('invalid-namespace', exc.condition)


    def test_streamDefaultNamespace(self):
        """
        Test stream error on missing dialback namespace.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='badns' "
                           "to='xmpp.example.com'>")

        self.assertEqual(3, len(self.output))
        exc = error.exceptionFromStreamError(self.output[1])
        self.assertEqual('invalid-namespace', exc.condition)


    def test_streamNoDialbackNamespace(self):
        """
        Test stream error on missing dialback namespace.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns='jabber:server' "
                           "to='xmpp.example.com'>")

        self.assertEqual(3, len(self.output))
        exc = error.exceptionFromStreamError(self.output[1])
        self.assertEqual('invalid-namespace', exc.condition)


    def test_streamBadDialbackNamespace(self):
        """
        Test stream error on missing dialback namespace.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='badns' "
                           "xmlns='jabber:server' "
                           "to='xmpp.example.com'>")

        self.assertEqual(3, len(self.output))
        exc = error.exceptionFromStreamError(self.output[1])
        self.assertEqual('invalid-namespace', exc.condition)


    def test_streamToUnknownHost(self):
        """
        Test stream error on stream's to attribute having unknown host.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='jabber:server' "
                           "to='badhost'>")

        self.assertEqual(3, len(self.output))
        exc = error.exceptionFromStreamError(self.output[1])
        self.assertEqual('host-unknown', exc.condition)


    def test_streamToOtherLocalHost(self):
        """
        The authenticator supports XMPP 1.0 streams.
        """
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                           "xmlns:db='jabber:server:dialback' "
                           "xmlns='jabber:server' "
                           "to='pubsub.xmpp.example.com' "
                           "version='1.0'>")

        self.assertEqual(2, len(self.output))
        self.assertEqual(jid.JID('pubsub.xmpp.example.com'),
                         self.xmlstream.thisEntity)

    def test_onResult(self):
        def cb(result):
            self.assertEqual(1, len(self.output))
            reply = self.output[0]
            self.assertEqual(self.originating, reply['to'])
            self.assertEqual(self.receiving, reply['from'])
            self.assertEqual('valid', reply['type'])

        def validateConnection(thisHost, otherHost, sid, key):
            self.assertEqual(thisHost, self.receiving)
            self.assertEqual(otherHost, self.originating)
            self.assertEqual(sid, self.sid)
            self.assertEqual(key, self.key)
            return defer.succeed(None)

        self.xmlstream.sid = self.sid
        self.service.validateConnection = validateConnection

        result = domish.Element((NS_DIALBACK, 'result'))
        result['to'] = self.receiving
        result['from'] = self.originating
        result.addContent(self.key)

        d = self.authenticator.onResult(result)
        d.addCallback(cb)
        return d


    def test_onResultFailure(self):
        class TestError(Exception):
            pass

        def cb(result):
            reply = self.output[0]
            self.assertEqual('invalid', reply['type'])
            self.assertEqual(1, len(self.flushLoggedErrors(TestError)))


        def validateConnection(thisHost, otherHost, sid, key):
            return defer.fail(TestError())

        self.xmlstream.sid = self.sid
        self.service.validateConnection = validateConnection

        result = domish.Element((NS_DIALBACK, 'result'))
        result['to'] = self.receiving
        result['from'] = self.originating
        result.addContent(self.key)

        d = self.authenticator.onResult(result)
        d.addCallback(cb)
        return d



class FakeService(object):
    domains = set(['example.org', 'pubsub.example.org'])
    defaultDomain = 'example.org'
    secret = 'mysecret'

    def __init__(self):
        self.dispatched = []

    def dispatch(self, xs, element):
        self.dispatched.append(element)



class XMPPS2SServerFactoryTest(unittest.TestCase):
    """
    Tests for L{component.XMPPS2SServerFactory}.
    """

    def setUp(self):
        self.service = FakeService()
        self.factory = server.XMPPS2SServerFactory(self.service)
        self.xmlstream = self.factory.buildProtocol(None)
        self.transport = StringTransport()
        self.xmlstream.thisEntity = jid.JID('example.org')
        self.xmlstream.otherEntity = jid.JID('example.com')


    def test_makeConnection(self):
        """
        A new connection increases the stream serial count. No logs by default.
        """
        self.xmlstream.makeConnection(self.transport)
        self.assertEqual(0, self.xmlstream.serial)
        self.assertEqual(1, self.factory.serial)
        self.assertIdentical(None, self.xmlstream.rawDataInFn)
        self.assertIdentical(None, self.xmlstream.rawDataOutFn)


    def test_makeConnectionLogTraffic(self):
        """
        Setting logTraffic should set up raw data loggers.
        """
        self.factory.logTraffic = True
        self.xmlstream.makeConnection(self.transport)
        self.assertNotIdentical(None, self.xmlstream.rawDataInFn)
        self.assertNotIdentical(None, self.xmlstream.rawDataOutFn)


    def test_onError(self):
        """
        An observer for stream errors should trigger onError to log it.
        """
        self.xmlstream.makeConnection(self.transport)

        class TestError(Exception):
            pass

        reason = failure.Failure(TestError())
        self.xmlstream.dispatch(reason, xmlstream.STREAM_ERROR_EVENT)
        self.assertEqual(1, len(self.flushLoggedErrors(TestError)))


    def test_connectionInitialized(self):
        """
        """
        self.xmlstream.makeConnection(self.transport)
        self.xmlstream.dispatch(self.xmlstream, xmlstream.STREAM_AUTHD_EVENT)


    def test_connectionLost(self):
        """
        """
        self.xmlstream.makeConnection(self.transport)
        self.xmlstream.dispatch(self.xmlstream, xmlstream.STREAM_AUTHD_EVENT)
        self.xmlstream.dispatch(None, xmlstream.STREAM_END_EVENT)


    def test_Element(self):
        self.xmlstream.makeConnection(self.transport)
        self.xmlstream.dispatch(self.xmlstream, xmlstream.STREAM_AUTHD_EVENT)

        stanza = domish.Element((None, "presence"))
        self.xmlstream.dispatch(stanza)
        self.assertEqual(1, len(self.service.dispatched))
        self.assertIdentical(stanza, self.service.dispatched[-1])


    def test_ElementNotAuthenticated(self):
        self.xmlstream.makeConnection(self.transport)

        stanza = domish.Element((None, "presence"))
        self.xmlstream.dispatch(stanza)
        self.assertEqual(0, len(self.service.dispatched))



class ServerServiceTest(unittest.TestCase):

    def setUp(self):
        self.output = []

        self.xmlstream = xmlstream.XmlStream(xmlstream.Authenticator())
        self.xmlstream.thisEntity = jid.JID('example.org')
        self.xmlstream.otherEntity = jid.JID('example.com')
        self.xmlstream.send = self.output.append

        self.router = component.Router()
        self.service = server.ServerService(self.router,
                                            secret='mysecret',
                                            domain='example.org')
        self.service.xmlstream = self.xmlstream


    def test_defaultDomainInDomains(self):
        """
        The default domain is part of the domains considered local.
        """
        self.assertIn(self.service.defaultDomain, self.service.domains)


    def test_dispatch(self):
        stanza = domish.Element((None, "presence"))
        stanza['to'] = 'user@example.org'
        stanza['from'] = 'other@example.com'
        self.service.dispatch(self.xmlstream, stanza)

        self.assertEqual(1, len(self.output))
        self.assertIdentical(stanza, self.output[-1])


    def test_dispatchNoTo(self):
        errors = []
        self.xmlstream.sendStreamError = errors.append

        stanza = domish.Element((None, "presence"))
        stanza['from'] = 'other@example.com'
        self.service.dispatch(self.xmlstream, stanza)

        self.assertEqual(1, len(errors))
