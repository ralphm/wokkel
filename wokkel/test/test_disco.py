# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.disco}.
"""

from twisted.internet import defer
from twisted.trial import unittest
from twisted.words.protocols.jabber.jid import JID
from zope.interface import implements

from wokkel import disco
from wokkel.subprotocols import XMPPHandler
from wokkel.test.helpers import TestableRequestHandlerMixin


NS_DISCO_INFO = 'http://jabber.org/protocol/disco#info'
NS_DISCO_ITEMS = 'http://jabber.org/protocol/disco#items'


class DiscoHandlerTest(unittest.TestCase, TestableRequestHandlerMixin):
    """
    Tests for L{disco.DiscoHandler}.
    """

    def setUp(self):
        self.service = disco.DiscoHandler()


    def test_onDiscoInfo(self):
        """
        C{onDiscoInfo} should process an info request and return a response.

        The request should be parsed, C{info} called with the extracted
        parameters, and then the result should be formatted into a proper
        response element.
        """
        xml = """<iq from='test@example.com' to='example.com'
                     type='get'>
                   <query xmlns='%s'/>
                 </iq>""" % NS_DISCO_INFO

        def cb(element):
            self.assertEqual('query', element.name)
            self.assertEqual(NS_DISCO_INFO, element.uri)
            self.assertEqual(NS_DISCO_INFO, element.identity.uri)
            self.assertEqual('dummy', element.identity['category'])
            self.assertEqual('generic', element.identity['type'])
            self.assertEqual('Generic Dummy Entity', element.identity['name'])
            self.assertEqual(NS_DISCO_INFO, element.feature.uri)
            self.assertEqual('jabber:iq:version', element.feature['var'])

        def info(requestor, target, nodeIdentifier):
            self.assertEqual(JID('test@example.com'), requestor)
            self.assertEqual(JID('example.com'), target)
            self.assertEqual('', nodeIdentifier)

            return defer.succeed([
                disco.DiscoIdentity('dummy', 'generic', 'Generic Dummy Entity'),
                disco.DiscoFeature('jabber:iq:version')
            ])

        self.service.info = info
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d

    def test_onDiscoInfoWithNode(self):
        """
        An info request for a node should return it in the response.
        """
        xml = """<iq from='test@example.com' to='example.com'
                     type='get'>
                   <query xmlns='%s' node='test'/>
                 </iq>""" % NS_DISCO_INFO

        def cb(element):
            self.assertTrue(element.hasAttribute('node'))
            self.assertEqual('test', element['node'])

        def info(requestor, target, nodeIdentifier):
            self.assertEqual('test', nodeIdentifier)

            return defer.succeed([
                disco.DiscoFeature('jabber:iq:version')
            ])

        self.service.info = info
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_onDiscoItems(self):
        """
        C{onDiscoItems} should process an items request and return a response.

        The request should be parsed, C{items} called with the extracted
        parameters, and then the result should be formatted into a proper
        response element.
        """
        xml = """<iq from='test@example.com' to='example.com'
                     type='get'>
                   <query xmlns='%s'/>
                 </iq>""" % NS_DISCO_ITEMS

        def cb(element):
            self.assertEqual('query', element.name)
            self.assertEqual(NS_DISCO_ITEMS, element.uri)
            self.assertEqual(NS_DISCO_ITEMS, element.item.uri)
            self.assertEqual('example.com', element.item['jid'])
            self.assertEqual('test', element.item['node'])
            self.assertEqual('Test node', element.item['name'])

        def items(requestor, target, nodeIdentifier):
            self.assertEqual(JID('test@example.com'), requestor)
            self.assertEqual(JID('example.com'), target)
            self.assertEqual('', nodeIdentifier)

            return defer.succeed([
                disco.DiscoItem(JID('example.com'), 'test', 'Test node'),
            ])

        self.service.items = items
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d

    def test_onDiscoItemsWithNode(self):
        """
        An items request for a node should return it in the response.
        """
        xml = """<iq from='test@example.com' to='example.com'
                     type='get'>
                   <query xmlns='%s' node='test'/>
                 </iq>""" % NS_DISCO_ITEMS

        def cb(element):
            self.assertTrue(element.hasAttribute('node'))
            self.assertEqual('test', element['node'])

        def items(requestor, target, nodeIdentifier):
            self.assertEqual('test', nodeIdentifier)

            return defer.succeed([
                disco.DiscoFeature('jabber:iq:version')
            ])

        self.service.items = items
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_info(self):
        """
        C{info} should gather disco info from sibling handlers.
        """
        discoItems = [disco.DiscoIdentity('dummy', 'generic',
                                          'Generic Dummy Entity'),
                      disco.DiscoFeature('jabber:iq:version')
        ]

        class DiscoResponder(XMPPHandler):
            implements(disco.IDisco)

            def getDiscoInfo(self, requestor, target, nodeIdentifier):
                if not nodeIdentifier:
                    return defer.succeed(discoItems)
                else:
                    return defer.succeed([])

        def cb(result):
            self.assertEquals(discoItems, result)

        self.service.parent = [self.service, DiscoResponder()]
        d = self.service.info(JID('test@example.com'), JID('example.com'), '')
        d.addCallback(cb)
        return d


    def test_items(self):
        """
        C{info} should gather disco items from sibling handlers.
        """
        discoItems = [disco.DiscoItem(JID('example.com'), 'test', 'Test node')]

        class DiscoResponder(XMPPHandler):
            implements(disco.IDisco)

            def getDiscoItems(self, requestor, target, nodeIdentifier):
                if not nodeIdentifier:
                    return defer.succeed(discoItems)
                else:
                    return defer.succeed([])

        def cb(result):
            self.assertEquals(discoItems, result)

        self.service.parent = [self.service, DiscoResponder()]
        d = self.service.items(JID('test@example.com'), JID('example.com'), '')
        d.addCallback(cb)
        return d
