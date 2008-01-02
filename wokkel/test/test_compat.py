# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# Copyright (c) 2008 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.compat}.
"""

from twisted.internet import defer, protocol
from twisted.trial import unittest
from twisted.words.xish import domish, utility
from wokkel.compat import toResponse, XmlStreamFactoryMixin

class DummyProtocol(protocol.Protocol, utility.EventDispatcher):
    """
    I am a protocol with an event dispatcher without further processing.

    This protocol is only used for testing XmlStreamFactoryMixin to make
    sure the bootstrap observers are added to the protocol instance.
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.observers = []

        utility.EventDispatcher.__init__(self)


class XmlStreamFactoryMixinTest(unittest.TestCase):

    def test_buildProtocol(self):
        """
        Test building of protocol.

        Arguments passed to Factory should be passed to protocol on
        instantiation. Bootstrap observers should be setup.
        """
        d = defer.Deferred()

        f = XmlStreamFactoryMixin(None, test=None)
        f.protocol = DummyProtocol
        f.addBootstrap('//event/myevent', d.callback)
        xs = f.buildProtocol(None)

        self.assertEquals(f, xs.factory)
        self.assertEquals((None,), xs.args)
        self.assertEquals({'test': None}, xs.kwargs)
        xs.dispatch(None, '//event/myevent')
        return d

    def test_addAndRemoveBootstrap(self):
        """
        Test addition and removal of a bootstrap event handler.
        """
        def cb(self):
            pass

        f = XmlStreamFactoryMixin(None, test=None)

        f.addBootstrap('//event/myevent', cb)
        self.assertIn(('//event/myevent', cb), f.bootstraps)

        f.removeBootstrap('//event/myevent', cb)
        self.assertNotIn(('//event/myevent', cb), f.bootstraps)

class ToResponseTest(unittest.TestCase):

    def test_toResponse(self):
        """
        Test that a response stanza is generated with addressing swapped.
        """
        stanza = domish.Element(('jabber:client', 'iq'))
        stanza['type'] = 'get'
        stanza['to'] = 'user1@example.com'
        stanza['from'] = 'user2@example.com/resource'
        stanza['id'] = 'stanza1'
        response = toResponse(stanza, 'result')
        self.assertNotIdentical(stanza, response)
        self.assertEqual(response['from'], 'user1@example.com')
        self.assertEqual(response['to'], 'user2@example.com/resource')
        self.assertEqual(response['type'], 'result')
        self.assertEqual(response['id'], 'stanza1')

    def test_toResponseNoFrom(self):
        """
        Test that a response is generated from a stanza without a from address.
        """
        stanza = domish.Element(('jabber:client', 'iq'))
        stanza['type'] = 'get'
        stanza['to'] = 'user1@example.com'
        response = toResponse(stanza)
        self.assertEqual(response['from'], 'user1@example.com')
        self.failIf(response.hasAttribute('to'))

    def test_toResponseNoTo(self):
        """
        Test that a response is generated from a stanza without a to address.
        """
        stanza = domish.Element(('jabber:client', 'iq'))
        stanza['type'] = 'get'
        stanza['from'] = 'user2@example.com/resource'
        response = toResponse(stanza)
        self.failIf(response.hasAttribute('from'))
        self.assertEqual(response['to'], 'user2@example.com/resource')

    def test_toResponseNoAddressing(self):
        """
        Test that a response is generated from a stanza without any addressing.
        """
        stanza = domish.Element(('jabber:client', 'message'))
        stanza['type'] = 'chat'
        response = toResponse(stanza)
        self.failIf(response.hasAttribute('to'))
        self.failIf(response.hasAttribute('from'))

    def test_noID(self):
        """
        Test that a proper response is generated without id attribute.
        """
        stanza = domish.Element(('jabber:client', 'message'))
        response = toResponse(stanza)
        self.failIf(response.hasAttribute('id'))
