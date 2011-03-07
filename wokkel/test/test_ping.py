# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.ping}.
"""

from zope.interface import verify

from twisted.internet import defer
from twisted.trial import unittest
from twisted.words.protocols.jabber.error import StanzaError
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import toResponse

from wokkel import disco, iwokkel, ping
from wokkel.generic import parseXml
from wokkel.test.helpers import XmlStreamStub

class PingClientProtocolTest(unittest.TestCase):
    """
    Tests for L{ping.PingClientProtocol}.
    """

    def setUp(self):
        self.stub = XmlStreamStub()
        self.protocol = ping.PingClientProtocol()
        self.protocol.xmlstream = self.stub.xmlstream
        self.protocol.connectionInitialized()


    def test_ping(self):
        """
        Pinging a service should fire a deferred with None
        """
        def cb(result):
            self.assertIdentical(None, result)

        d = self.protocol.ping(JID("example.com"))
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEqual(u'example.com', iq.getAttribute(u'to'))
        self.assertEqual(u'get', iq.getAttribute(u'type'))
        self.assertEqual('urn:xmpp:ping', iq.ping.uri)

        response = toResponse(iq, u'result')
        self.stub.send(response)

        return d


    def test_pingWithSender(self):
        """
        Pinging a service with a sender address should include that address.
        """
        d = self.protocol.ping(JID("example.com"),
                               sender=JID('user@example.com'))

        iq = self.stub.output[-1]
        self.assertEqual(u'user@example.com', iq.getAttribute(u'from'))

        response = toResponse(iq, u'result')
        self.stub.send(response)

        return d


    def test_pingNotSupported(self):
        """
        Pinging a service should fire a deferred with None if not supported.
        """
        def cb(result):
            self.assertIdentical(None, result)

        d = self.protocol.ping(JID("example.com"))
        d.addCallback(cb)

        iq = self.stub.output[-1]

        exc = StanzaError('service-unavailable')
        response = exc.toResponse(iq)
        self.stub.send(response)

        return d


    def test_pingStanzaError(self):
        """
        Pinging a service should errback a deferred on other (stanza) errors.
        """
        def cb(exc):
            self.assertEquals('item-not-found', exc.condition)

        d = self.protocol.ping(JID("example.com"))
        self.assertFailure(d, StanzaError)
        d.addCallback(cb)

        iq = self.stub.output[-1]

        exc = StanzaError('item-not-found')
        response = exc.toResponse(iq)
        self.stub.send(response)

        return d



class PingHandlerTest(unittest.TestCase):
    """
    Tests for L{ping.PingHandler}.
    """

    def setUp(self):
        self.stub = XmlStreamStub()
        self.protocol = ping.PingHandler()
        self.protocol.xmlstream = self.stub.xmlstream
        self.protocol.connectionInitialized()


    def test_onPing(self):
        """
        A ping should have a simple result response.
        """
        xml = """<iq from='test@example.com' to='example.com' type='get'>
                   <ping xmlns='urn:xmpp:ping'/>
                 </iq>"""
        self.stub.send(parseXml(xml))

        response = self.stub.output[-1]
        self.assertEquals('example.com', response.getAttribute('from'))
        self.assertEquals('test@example.com', response.getAttribute('to'))
        self.assertEquals('result', response.getAttribute('type'))


    def test_onPingHandled(self):
        """
        The ping handler should mark the stanza as handled.
        """
        xml = """<iq from='test@example.com' to='example.com' type='get'>
                   <ping xmlns='urn:xmpp:ping'/>
                 </iq>"""
        iq = parseXml(xml)
        self.stub.send(iq)

        self.assertTrue(iq.handled)


    def test_interfaceIDisco(self):
        """
        The ping handler should provice Service Discovery information.
        """
        verify.verifyObject(iwokkel.IDisco, self.protocol)


    def test_getDiscoInfo(self):
        """
        The ping namespace should be returned as a supported feature.
        """
        def cb(info):
            discoInfo = disco.DiscoInfo()
            for item in info:
                discoInfo.append(item)
            self.assertIn('urn:xmpp:ping', discoInfo.features)

        d = defer.maybeDeferred(self.protocol.getDiscoInfo,
                                JID('user@example.org/home'),
                                JID('pubsub.example.org'),
                                '')
        d.addCallback(cb)
        return d


    def test_getDiscoInfoNode(self):
        """
        The ping namespace should not be returned for a node.
        """
        def cb(info):
            discoInfo = disco.DiscoInfo()
            for item in info:
                discoInfo.append(item)
            self.assertNotIn('urn:xmpp:ping', discoInfo.features)

        d = defer.maybeDeferred(self.protocol.getDiscoInfo,
                                JID('user@example.org/home'),
                                JID('pubsub.example.org'),
                                'test')
        d.addCallback(cb)
        return d


    def test_getDiscoItems(self):
        """
        Items are not supported by this handler, so an empty list is expected.
        """
        def cb(items):
            self.assertEquals(0, len(items))

        d = defer.maybeDeferred(self.protocol.getDiscoItems,
                                JID('user@example.org/home'),
                                JID('pubsub.example.org'),
                                '')
        d.addCallback(cb)
        return d
