# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.generic}.
"""

from twisted.trial import unittest
from twisted.words.xish import domish
from twisted.words.protocols.jabber.jid import JID

from wokkel import generic
from wokkel.test.helpers import XmlStreamStub

NS_VERSION = 'jabber:iq:version'

class VersionHandlerTest(unittest.TestCase):
    """
    Tests for L{wokkel.generic.VersionHandler}.
    """

    def test_onVersion(self):
        """
        Test response to incoming version request.
        """
        self.stub = XmlStreamStub()
        self.protocol = generic.VersionHandler('Test', '0.1.0')
        self.protocol.xmlstream = self.stub.xmlstream
        self.protocol.send = self.stub.xmlstream.send
        self.protocol.connectionInitialized()

        iq = domish.Element((None, 'iq'))
        iq['from'] = 'user@example.org/Home'
        iq['to'] = 'example.org'
        iq['type'] = 'get'
        iq.addElement((NS_VERSION, 'query'))
        self.stub.send(iq)

        response = self.stub.output[-1]
        self.assertEquals('user@example.org/Home', response['to'])
        self.assertEquals('example.org', response['from'])
        self.assertEquals('result', response['type'])
        self.assertEquals(NS_VERSION, response.query.uri)
        elements = list(domish.generateElementsQNamed(response.query.children,
                                                      'name', NS_VERSION))
        self.assertEquals(1, len(elements))
        self.assertEquals('Test', unicode(elements[0]))
        elements = list(domish.generateElementsQNamed(response.query.children,
                                                      'version', NS_VERSION))
        self.assertEquals(1, len(elements))
        self.assertEquals('0.1.0', unicode(elements[0]))



class XmlPipeTest(unittest.TestCase):
    """
    Tests for L{wokkel.generic.XmlPipe}.
    """

    def setUp(self):
        self.pipe = generic.XmlPipe()


    def test_sendFromSource(self):
        """
        Send an element from the source and observe it from the sink.
        """
        def cb(obj):
            called.append(obj)

        called = []
        self.pipe.sink.addObserver('/test[@xmlns="testns"]', cb)
        element = domish.Element(('testns', 'test'))
        self.pipe.source.send(element)
        self.assertEquals([element], called)


    def test_sendFromSink(self):
        """
        Send an element from the sink and observe it from the source.
        """
        def cb(obj):
            called.append(obj)

        called = []
        self.pipe.source.addObserver('/test[@xmlns="testns"]', cb)
        element = domish.Element(('testns', 'test'))
        self.pipe.sink.send(element)
        self.assertEquals([element], called)



class RequestTest(unittest.TestCase):
    """
    Tests for L{generic.Request}.
    """

    def setUp(self):
        self.request = generic.Request()


    def test_toElementStanzaKind(self):
        """
        A request is an iq stanza.
        """
        element = self.request.toElement()
        self.assertIdentical(None, element.uri)
        self.assertEquals('iq', element.name)


    def test_toElementStanzaType(self):
        """
        The request has type 'get'.
        """
        self.assertEquals('get', self.request.stanzaType)
        element = self.request.toElement()
        self.assertEquals('get', element.getAttribute('type'))


    def test_toElementStanzaTypeSet(self):
        """
        The request has type 'set'.
        """
        self.request.stanzaType = 'set'
        element = self.request.toElement()
        self.assertEquals('set', element.getAttribute('type'))


    def test_toElementStanzaID(self):
        """
        A request, when rendered, has an identifier.
        """
        element = self.request.toElement()
        self.assertNotIdentical(None, self.request.stanzaID)
        self.assertEquals(self.request.stanzaID, element.getAttribute('id'))


    def test_toElementRecipient(self):
        """
        A request without recipient, has no 'to' attribute.
        """
        self.request = generic.Request(recipient=JID('other@example.org'))
        self.assertEquals(JID('other@example.org'), self.request.recipient)
        element = self.request.toElement()
        self.assertEquals(u'other@example.org', element.getAttribute('to'))


    def test_toElementRecipientNone(self):
        """
        A request without recipient, has no 'to' attribute.
        """
        element = self.request.toElement()
        self.assertFalse(element.hasAttribute('to'))


    def test_toElementSender(self):
        """
        A request with sender, has a 'from' attribute.
        """
        self.request = generic.Request(sender=JID('user@example.org'))
        self.assertEquals(JID('user@example.org'), self.request.sender)
        element = self.request.toElement()
        self.assertEquals(u'user@example.org', element.getAttribute('from'))


    def test_toElementSenderNone(self):
        """
        A request without sender, has no 'from' attribute.
        """
        element = self.request.toElement()
        self.assertFalse(element.hasAttribute('from'))


    def test_timeoutDefault(self):
        """
        The default is no timeout.
        """
        self.assertIdentical(None, self.request.timeout)
