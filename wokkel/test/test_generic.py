# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.generic}.
"""

from twisted.trial import unittest
from twisted.words.xish import domish

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
        query = iq.addElement((NS_VERSION, 'query'))
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
