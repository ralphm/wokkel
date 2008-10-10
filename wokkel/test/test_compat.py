# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# Copyright (c) 2008 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.compat}.
"""

from twisted.internet import defer, protocol
from twisted.trial import unittest
from twisted.words.xish import domish, utility
from wokkel.compat import toResponse, BootstrapMixin

class DummyProtocol(protocol.Protocol, utility.EventDispatcher):
    """
    I am a protocol with an event dispatcher without further processing.

    This protocol is only used for testing BootstrapMixin to make
    sure the bootstrap observers are added to the protocol instance.
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.observers = []

        utility.EventDispatcher.__init__(self)



class BootstrapMixinTest(unittest.TestCase):
    """
    Tests for L{BootstrapMixin}.

    @ivar factory: Instance of the factory or mixin under test.
    """

    def setUp(self):
        self.factory = BootstrapMixin()


    def test_installBootstraps(self):
        """
        Dispatching an event should fire registered bootstrap observers.
        """
        d = defer.Deferred()
        dispatcher = DummyProtocol()
        self.factory.addBootstrap('//event/myevent', d.callback)
        self.factory.installBootstraps(dispatcher)
        dispatcher.dispatch(None, '//event/myevent')
        return d


    def test_addAndRemoveBootstrap(self):
        """
        Test addition and removal of a bootstrap event handler.
        """
        def cb(self):
            pass

        self.factory.addBootstrap('//event/myevent', cb)
        self.assertIn(('//event/myevent', cb), self.factory.bootstraps)

        self.factory.removeBootstrap('//event/myevent', cb)
        self.assertNotIn(('//event/myevent', cb), self.factory.bootstraps)



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
