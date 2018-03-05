# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.generic}.
"""

from __future__ import division, absolute_import

import re

from zope.interface.verify import verifyObject

from twisted.python import deprecate
from twisted.python.compat import unicode
from twisted.trial import unittest
from twisted.trial.util import suppress as SUPPRESS
from twisted.words.xish import domish
from twisted.words.protocols.jabber.jid import JID

from incremental import Version

from wokkel import generic
from wokkel.iwokkel import IDisco
from wokkel.test.helpers import XmlStreamStub

NS_VERSION = 'jabber:iq:version'

class VersionHandlerTest(unittest.TestCase):
    """
    Tests for L{wokkel.generic.VersionHandler}.
    """

    def setUp(self):
        self.protocol = generic.VersionHandler('Test', '0.1.0')


    def test_interface(self):
        """
        L{generic.VersionHandler} implements {IDisco}.
        """
        verifyObject(IDisco, self.protocol)


    def test_onVersion(self):
        """
        Test response to incoming version request.
        """
        self.stub = XmlStreamStub()
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



class StanzaTest(unittest.TestCase):
    """
    Tests for L{generic.Stanza}.
    """

    def test_fromElement(self):
        xml = """
        <message type='chat' from='other@example.org' to='user@example.org'/>
        """

        stanza = generic.Stanza.fromElement(generic.parseXml(xml))
        self.assertEqual('chat', stanza.stanzaType)
        self.assertEqual(JID('other@example.org'), stanza.sender)
        self.assertEqual(JID('user@example.org'), stanza.recipient)


    def test_fromElementChildParser(self):
        """
        Child elements for which no parser is defined are ignored.
        """
        xml = """
        <message from='other@example.org' to='user@example.org'>
          <x xmlns='http://example.org/'/>
        </message>
        """

        class Message(generic.Stanza):
            childParsers = {('http://example.org/', 'x'): '_childParser_x'}
            elements = []

            def _childParser_x(self, element):
                self.elements.append(element)

        message = Message.fromElement(generic.parseXml(xml))
        self.assertEqual(1, len(message.elements))


    def test_fromElementChildParserAll(self):
        """
        Child elements for which no parser is defined are ignored.
        """
        xml = """
        <message from='other@example.org' to='user@example.org'>
          <x xmlns='http://example.org/'/>
        </message>
        """

        class Message(generic.Stanza):
            childParsers = {None: '_childParser'}
            elements = []

            def _childParser(self, element):
                self.elements.append(element)

        message = Message.fromElement(generic.parseXml(xml))
        self.assertEqual(1, len(message.elements))


    def test_fromElementChildParserUnknown(self):
        """
        Child elements for which no parser is defined are ignored.
        """
        xml = """
        <message from='other@example.org' to='user@example.org'>
          <x xmlns='http://example.org/'/>
        </message>
        """
        generic.Stanza.fromElement(generic.parseXml(xml))




class RequestTest(unittest.TestCase):
    """
    Tests for L{generic.Request}.
    """

    def setUp(self):
        self.request = generic.Request()


    def test_requestParser(self):
        """
        The request's child element is passed to requestParser.
        """
        xml = """
        <iq type='get'>
          <query xmlns='jabber:iq:version'/>
        </iq>
        """

        class VersionRequest(generic.Request):
            elements = []

            def parseRequest(self, element):
                self.elements.append((element.uri, element.name))

        request = VersionRequest.fromElement(generic.parseXml(xml))
        self.assertEqual([(NS_VERSION, 'query')], request.elements)


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


    def test_stanzaTypeInit(self):
        """
        If stanzaType is passed in __init__, it overrides the class variable.
        """

        class SetRequest(generic.Request):
            stanzaType = 'set'

        request = SetRequest(stanzaType='get')
        self.assertEqual('get', request.stanzaType)


    def test_stanzaTypeClass(self):
        """
        If stanzaType is not passed in __init__, the class variable is used.
        """

        class SetRequest(generic.Request):
            stanzaType = 'set'

        request = SetRequest()
        self.assertEqual('set', request.stanzaType)



class PrepareIDNNameTests(unittest.TestCase):
    """
    Tests for L{wokkel.generic.prepareIDNName}.
    """

    suppress = [SUPPRESS(category=DeprecationWarning,
                         message=re.escape(
                             deprecate.getDeprecationWarningString(
                                 generic.prepareIDNName,
                                 Version("wokkel", 18, 0, 0, release_candidate=4),
                                 replacement="unicode.encode('idna')")))]


    def test_deprecated(self):
        """
        prepareIDNName is deprecated.
        """
        self.callDeprecated((Version("wokkel", 18, 0, 0, release_candidate=4),
                             "unicode.encode('idna')"),
                            generic.prepareIDNName, ("example.com"))
    test_deprecated.suppress = []


    def test_unicode(self):
        """
        A unicode all-ASCII name is converted to an ASCII byte string.
        """
        name = u"example.com"
        result = generic.prepareIDNName(name)
        self.assertEqual(b"example.com", result)


    def test_unicodeNonASCII(self):
        """
        A unicode with non-ASCII is converted to its ACE equivalent.
        """
        name = u"\u00e9chec.example.com"
        result = generic.prepareIDNName(name)
        self.assertEqual(b"xn--chec-9oa.example.com", result)


    def test_unicodeHalfwidthIdeographicFullStop(self):
        """
        Exotic dots in unicode names are converted to Full Stop.
        """
        name = u"\u00e9chec.example\uff61com"
        result = generic.prepareIDNName(name)
        self.assertEqual(b"xn--chec-9oa.example.com", result)


    def test_unicodeTrailingDot(self):
        """
        Unicode names with trailing dots retain the trailing dot.

        L{encodings.idna.ToASCII} doesn't allow the empty string as the input,
        hence the implementation needs to strip a trailing dot, and re-add it
        after encoding the labels.
        """
        name = u"example.com."
        result = generic.prepareIDNName(name)
        self.assertEqual(b"example.com.", result)
