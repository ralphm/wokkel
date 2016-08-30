# -*- coding: utf-8 -*-
#
# Copyright (c) Adrien Cossa, Jérôme Poisson
# See LICENSE for details.

"""
Tests for L{wokkel.rsm}.
"""

from zope.interface import verify

from twisted.trial import unittest
from twisted.words.xish import domish
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import toResponse
from twisted.internet import defer

from wokkel.generic import parseXml
from wokkel import iwokkel, pubsub
from wokkel.rsm import NS_RSM, RSMRequest, RSMResponse, PubSubClient, PubSubService
from wokkel.test.helpers import XmlStreamStub, TestableRequestHandlerMixin

import uuid

RSMResponse.__eq__ = lambda self, other: self.first == other.first and\
    self.last == other.last and\
    self.index == other.index and\
    self.count == other.count

class RSMRequestTest(unittest.TestCase):
    """
    Tests for L{rsm.RSMRequest}.
    """

    def test___init__(self):
        """
        Fail to initialize a RSMRequest with wrong attribute values.
        """
        self.assertRaises(AssertionError, RSMRequest, index=371, after=u'test')
        self.assertRaises(AssertionError, RSMRequest, index=371, before=u'test')
        self.assertRaises(AssertionError, RSMRequest, before=117)
        self.assertRaises(AssertionError, RSMRequest, after=312)
        self.assertRaises(AssertionError, RSMRequest, after=u'117', before=u'312')

    def test_parse(self):
        """
        Parse a request element asking for the first page.
        """
        xml = """
        <query xmlns='jabber:iq:search'>
          <nick>Pete</nick>
          <set xmlns='http://jabber.org/protocol/rsm'>
            <max>1</max>
          </set>
        </query>
        """
        request = RSMRequest.fromElement(parseXml(xml))
        self.assertEqual(1, request.max)
        self.assertIdentical(None, request.index)
        self.assertIdentical(None, request.after)
        self.assertIdentical(None, request.before)

    def test_parseSecondPage(self):
        """
        Parse a request element asking for a next page.
        """
        xml = """
        <query xmlns='jabber:iq:search'>
          <nick>Pete</nick>
          <set xmlns='http://jabber.org/protocol/rsm'>
            <max>3</max>
            <after>peterpan@neverland.lit</after>
          </set>
        </query>
        """
        request = RSMRequest.fromElement(parseXml(xml))
        self.assertEqual(3, request.max)
        self.assertIdentical(None, request.index)
        self.assertEqual(u'peterpan@neverland.lit', request.after)
        self.assertIdentical(None, request.before)

    def test_parsePreviousPage(self):
        """
        Parse a request element asking for a previous page.
        """
        xml = """
        <query xmlns='jabber:iq:search'>
          <nick>Pete</nick>
          <set xmlns='http://jabber.org/protocol/rsm'>
            <max>5</max>
            <before>peterpan@pixyland.org</before>
          </set>
        </query>
        """
        request = RSMRequest.fromElement(parseXml(xml))
        self.assertEqual(5, request.max)
        self.assertIdentical(None, request.index)
        self.assertIdentical(None, request.after)
        self.assertEqual(u'peterpan@pixyland.org', request.before)

    def test_parseLastPage(self):
        """
        Parse a request element asking for the last page.
        """
        xml = """
        <query xmlns='jabber:iq:search'>
          <nick>Pete</nick>
          <set xmlns='http://jabber.org/protocol/rsm'>
            <max>7</max>
            <before/>
          </set>
        </query>
        """
        request = RSMRequest.fromElement(parseXml(xml))
        self.assertEqual(7, request.max)
        self.assertIdentical(None, request.index)
        self.assertIdentical(None, request.after)
        self.assertEqual('', request.before)

    def test_parseOutOfOrderPage(self):
        """
        Parse a request element asking for a page out of order.
        """
        xml = """
        <query xmlns='jabber:iq:search'>
          <nick>Pete</nick>
          <set xmlns='http://jabber.org/protocol/rsm'>
            <max>9</max>
            <index>371</index>
          </set>
        </query>
        """
        request = RSMRequest.fromElement(parseXml(xml))
        self.assertEqual(9, request.max)
        self.assertEqual(371, request.index)
        self.assertIdentical(None, request.after)
        self.assertIdentical(None, request.before)

    def test_parseItemCount(self):
        """
        Parse a request element asking for the items count.
        """
        xml = """
        <query xmlns='jabber:iq:search'>
          <nick>Pete</nick>
          <set xmlns='http://jabber.org/protocol/rsm'>
            <max>0</max>
          </set>
        </query>
        """
        request = RSMRequest.fromElement(parseXml(xml))
        self.assertEqual(0, request.max)
        self.assertIdentical(None, request.index)
        self.assertIdentical(None, request.after)
        self.assertIdentical(None, request.before)

    def test_render(self):
        """
        Embed a page request in the element.
        """
        element = domish.Element(('jabber:iq:search', 'query'))
        element.addElement('items')['max_items'] = u'10'
        RSMRequest(1).render(element)

        self.assertEqual(u'10', element.items['max_items'])  # not changed

        self.assertEqual(NS_RSM, element.set.uri)
        self.assertEqual(u'1', ''.join(element.set.max.children))
        self.assertIdentical(None, element.set.after)
        self.assertIdentical(None, element.set.before)
        self.assertIdentical(None, element.set.index)

    def test_renderPubSub(self):
        """
        Embed a page request in the pubsub element.
        """
        element = domish.Element((pubsub.NS_PUBSUB, 'pubsub'))
        element.addElement('items')['max_items'] = u'10'
        RSMRequest(3).render(element)

        self.assertEqual(u'10', element.items['max_items'])  # not changed

        self.assertEqual(NS_RSM, element.set.uri)
        self.assertEqual(u'3', ''.join(element.set.max.children))
        self.assertIdentical(None, element.set.after)
        self.assertIdentical(None, element.set.before)
        self.assertIdentical(None, element.set.index)

    def test_renderItems(self):
        """
        Embed a page request in the element, specify items.
        """
        element = domish.Element(('jabber:iq:search', 'query'))
        RSMRequest(5, index=127).render(element)
        self.assertEqual(NS_RSM, element.set.uri)
        self.assertEqual(u'5', ''.join(element.set.max.children))
        self.assertIdentical(None, element.set.after)
        self.assertIdentical(None, element.set.before)
        self.assertEqual(u'127', ''.join(element.set.index.children))

    def test_renderAfter(self):
        """
        Embed a page request in the element, specify after.
        """
        element = domish.Element(('jabber:iq:search', 'query'))
        RSMRequest(5, after=u'test').render(element)
        self.assertEqual(NS_RSM, element.set.uri)
        self.assertEqual(u'5', ''.join(element.set.max.children))
        self.assertEqual(u'test', ''.join(element.set.after.children))
        self.assertIdentical(None, element.set.before)
        self.assertIdentical(None, element.set.index)

    def test_renderBefore(self):
        """
        Embed a page request in the element, specify before.
        """
        element = domish.Element(('jabber:iq:search', 'query'))
        RSMRequest(5, before=u'test').render(element)
        self.assertEqual(NS_RSM, element.set.uri)
        self.assertEqual(u'5', ''.join(element.set.max.children))
        self.assertIdentical(None, element.set.after)
        self.assertEqual(u'test', ''.join(element.set.before.children))
        self.assertIdentical(None, element.set.index)


class RSMResponseTest(unittest.TestCase):
    """
    Tests for L{rsm.RSMResponse}.
    """

    def test___init__(self):
        """
        Fail to initialize a RSMResponse with wrong attribute values.
        """
        self.assertRaises(AssertionError, RSMResponse, index=127, first=u'127')
        self.assertRaises(AssertionError, RSMResponse, index=127, last=u'351')

    def test_parse(self):
        """
        Parse a response element returning a page.
        """
        xml = """
        <query xmlns='jabber:iq:search'>
          <set xmlns='http://jabber.org/protocol/rsm'>
            <first index='20'>stpeter@jabber.org</first>
            <last>peterpan@neverland.lit</last>
            <count>800</count>
          </set>
        </query>
        """
        response = RSMResponse.fromElement(parseXml(xml))
        self.assertEqual(800, response.count)
        self.assertEqual(20, response.index)
        self.assertEqual(u'stpeter@jabber.org', response.first)
        self.assertEqual(u'peterpan@neverland.lit', response.last)

    def test_parseEmptySet(self):
        """
        Parse a response element returning an empty set.
        """
        xml = """
        <query xmlns='jabber:iq:search'>
          <set xmlns='http://jabber.org/protocol/rsm'>
            <count>800</count>
          </set>
        </query>
        """
        response = RSMResponse.fromElement(parseXml(xml))
        self.assertEqual(800, response.count)
        self.assertIdentical(None, response.first)
        self.assertIdentical(None, response.last)
        self.assertIdentical(None, response.index)

    def test_render(self):
        """
        Embed a page response in the element.
        """
        element = domish.Element(('jabber:iq:search', 'query'))
        RSMResponse(u'stpeter@jabber.org', u'peterpan@neverland.lit', 20, 800).render(element)

        self.assertEqual(NS_RSM, element.set.uri)
        self.assertEqual(u'800', ''.join(element.set.count.children))
        self.assertEqual(u'stpeter@jabber.org',
                         ''.join(element.set.first.children))
        self.assertEqual(u'peterpan@neverland.lit',
                         ''.join(element.set.last.children))
        self.assertEqual(u'20', element.set.first['index'])

    def test_renderEmptySet(self):
        """
        Embed a page response in the element, for empty set.
        """
        element = domish.Element(('jabber:iq:search', 'query'))
        RSMResponse(count=800).render(element)

        self.assertEqual(NS_RSM, element.set.uri)
        self.assertEqual(u'800', ''.join(element.set.count.children))
        self.assertIdentical(None, element.set.first)
        self.assertIdentical(None, element.set.last)


class PubSubClientTest(unittest.TestCase):
    """
    Tests for L{rsm.PubSubClient}.
    """
    timeout = 2

    def setUp(self):
        self.stub = XmlStreamStub()
        self.protocol = PubSubClient()
        self.protocol.xmlstream = self.stub.xmlstream
        self.protocol.connectionInitialized()

    def test_items(self):
        """
        Test sending items request to get the first page.
        """
        def cb(response):
            items, rsm = response
            self.assertEquals(2, len(items))
            self.assertEquals([item1, item2], items)
            self.assertEquals(rsm, RSMResponse('item1', 'item2', 0, 800))

        d = self.protocol.items(JID('pubsub.example.org'), 'test',
                                rsm_request=RSMRequest(2))
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('get', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(pubsub.NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'items', pubsub.NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])

        set_elts = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'set', NS_RSM))
        self.assertEquals(1, len(set_elts))
        set_elt = set_elts[0]
        self.assertEquals(u'2', ''.join(set_elt.max.children))

        response = toResponse(iq, 'result')
        items = response.addElement((pubsub.NS_PUBSUB,
                                     'pubsub')).addElement('items')
        items['node'] = 'test'
        item1 = items.addElement('item')
        item1['id'] = 'item1'
        item2 = items.addElement('item')
        item2['id'] = 'item2'
        RSMResponse(u'item1', u'item2', 0, 800).render(response.pubsub)
        self.stub.send(response)

        return d

    def test_itemsAfter(self):
        """
        Test sending items request to get the next page.
        """
        def cb(response):
            items, rsm = response
            self.assertEquals(2, len(items))
            self.assertEquals([item1, item2], items)
            self.assertEquals(rsm, RSMResponse('item3', 'item4', 2, 800))

        d = self.protocol.items(JID('pubsub.example.org'), 'test',
                                rsm_request=RSMRequest(2, after=u'item2'))
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('get', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(pubsub.NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'items', pubsub.NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])

        set_elts = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'set', NS_RSM))
        self.assertEquals(1, len(set_elts))
        set_elt = set_elts[0]
        self.assertEquals(u'2', ''.join(set_elt.max.children))
        self.assertEquals(u'item2', ''.join(set_elt.after.children))

        response = toResponse(iq, 'result')
        items = response.addElement((pubsub.NS_PUBSUB,
                                     'pubsub')).addElement('items')
        items['node'] = 'test'
        item1 = items.addElement('item')
        item1['id'] = 'item3'
        item2 = items.addElement('item')
        item2['id'] = 'item4'
        RSMResponse(u'item3', u'item4', 2, 800).render(response.pubsub)
        self.stub.send(response)

        return d

    def test_itemsBefore(self):
        """
        Test sending items request to get the previous page.
        """
        def cb(response):
            items, rsm = response
            self.assertEquals(2, len(items))
            self.assertEquals([item1, item2], items)
            self.assertEquals(rsm, RSMResponse('item1', 'item2', 0, 800))

        d = self.protocol.items(JID('pubsub.example.org'), 'test',
                                rsm_request=RSMRequest(2, before=u'item3'))
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('get', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(pubsub.NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'items', pubsub.NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])

        set_elts = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'set', NS_RSM))
        self.assertEquals(1, len(set_elts))
        set_elt = set_elts[0]
        self.assertEquals(u'2', ''.join(set_elt.max.children))
        self.assertEquals(u'item3', ''.join(set_elt.before.children))

        response = toResponse(iq, 'result')
        items = response.addElement((pubsub.NS_PUBSUB,
                                     'pubsub')).addElement('items')
        items['node'] = 'test'
        item1 = items.addElement('item')
        item1['id'] = 'item1'
        item2 = items.addElement('item')
        item2['id'] = 'item2'
        RSMResponse(u'item1', u'item2', 0, 800).render(response.pubsub)
        self.stub.send(response)

        return d

    def test_itemsIndex(self):
        """
        Test sending items request to get a page out of order.
        """
        def cb(response):
            items, rsm = response
            self.assertEquals(3, len(items))
            self.assertEquals([item1, item2, item3], items)
            self.assertEquals(rsm, RSMResponse('item4', 'item6', 3, 800))

        d = self.protocol.items(JID('pubsub.example.org'), 'test',
                                rsm_request=RSMRequest(3, index=3))
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('get', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(pubsub.NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'items', pubsub.NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])

        set_elts = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'set', NS_RSM))
        self.assertEquals(1, len(set_elts))
        set_elt = set_elts[0]
        self.assertEquals(u'3', ''.join(set_elt.max.children))
        self.assertEquals(u'3', ''.join(set_elt.index.children))

        response = toResponse(iq, 'result')
        items = response.addElement((pubsub.NS_PUBSUB,
                                     'pubsub')).addElement('items')
        items['node'] = 'test'
        item1 = items.addElement('item')
        item1['id'] = 'item4'
        item2 = items.addElement('item')
        item2['id'] = 'item5'
        item3 = items.addElement('item')
        item3['id'] = 'item6'
        RSMResponse(u'item4', u'item6', 3, 800).render(response.pubsub)
        self.stub.send(response)

        return d

    def test_itemsCount(self):
        """
        Test sending items request to count them.
        """
        def cb(response):
            items, rsm = response
            self.assertEquals(0, len(items))
            self.assertEquals(rsm, RSMResponse(count=800))

        d = self.protocol.items(JID('pubsub.example.org'), 'test',
                                rsm_request=RSMRequest(0))
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('get', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(pubsub.NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'items', pubsub.NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])

        set_elts = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'set', NS_RSM))
        self.assertEquals(1, len(set_elts))
        set_elt = set_elts[0]
        self.assertEquals(u'0', ''.join(set_elt.max.children))

        response = toResponse(iq, 'result')
        response.addElement((pubsub.NS_PUBSUB, 'pubsub'))
        RSMResponse(count=800).render(response.pubsub)
        self.stub.send(response)

        return d


class PubSubServiceTest(unittest.TestCase, TestableRequestHandlerMixin):

    def setUp(self):
        self.stub = XmlStreamStub()
        self.resource = pubsub.PubSubResource()
        self.service = PubSubService(self.resource)
        self.service.send = self.stub.xmlstream.send

    def test_on_items(self):
        """
        On a items request, return the first item for the given node.
        """
        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <items node='test'/>
          </pubsub>
          <set xmlns='http://jabber.org/protocol/rsm'>
            <max>1</max>
          </set>
        </iq>
        """

        def items(request):
            rsm = RSMResponse(u'item', u'item', 0, 800).toElement()
            return defer.succeed([pubsub.Item('current'), rsm])

        def cb(element):
            self.assertEqual(pubsub.NS_PUBSUB, element.uri)
            self.assertEqual(pubsub.NS_PUBSUB, element.items.uri)
            self.assertEqual(1, len(element.items.children))
            item = element.items.children[-1]
            self.assertTrue(domish.IElement.providedBy(item))
            self.assertEqual('item', item.name)
            self.assertEqual(pubsub.NS_PUBSUB, item.uri)
            self.assertEqual('current', item['id'])
            self.assertEqual(NS_RSM, element.set.uri)
            self.assertEqual('800', ''.join(element.set.count.children))
            self.assertEqual('0', element.set.first['index'])
            self.assertEqual('item', ''.join(element.set.first.children))
            self.assertEqual('item', ''.join(element.set.last.children))

        self.resource.items = items
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d

    def test_on_itemsIndex(self):
        """
        On a items request, return some items out of order for the given node.
        """
        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <items node='test'/>
          </pubsub>
          <set xmlns='http://jabber.org/protocol/rsm'>
            <max>2</max>
            <index>3</index>
          </set>
        </iq>
        """

        def items(request):
            rsm = RSMResponse(u'i1', u'i2', 3, 800).toElement()
            return defer.succeed([pubsub.Item('i1'), pubsub.Item('i2'), rsm])

        def cb(element):
            self.assertEqual(pubsub.NS_PUBSUB, element.uri)
            self.assertEqual(pubsub.NS_PUBSUB, element.items.uri)
            self.assertEqual(2, len(element.items.children))
            item = element.items.children[0]
            self.assertTrue(domish.IElement.providedBy(item))
            self.assertEqual('item', item.name)
            self.assertEqual(pubsub.NS_PUBSUB, item.uri)
            self.assertEqual('i1', item['id'])
            item = element.items.children[1]
            self.assertTrue(domish.IElement.providedBy(item))
            self.assertEqual('item', item.name)
            self.assertEqual(pubsub.NS_PUBSUB, item.uri)
            self.assertEqual('i2', item['id'])
            self.assertEqual(NS_RSM, element.set.uri)
            self.assertEqual('800', ''.join(element.set.count.children))
            self.assertEqual('3', element.set.first['index'])
            self.assertEqual('i1', ''.join(element.set.first.children))
            self.assertEqual('i2', ''.join(element.set.last.children))

        self.resource.items = items
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d

    def test_on_itemsCount(self):
        """
        On a items request, return the items count.
        """
        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <items node='test'/>
          </pubsub>
          <set xmlns='http://jabber.org/protocol/rsm'>
            <max>0</max>
          </set>
        </iq>
        """

        def items(request):
            rsm = RSMResponse(count=800).toElement()
            return defer.succeed([rsm])

        def cb(element):
            self.assertEqual(pubsub.NS_PUBSUB, element.uri)
            self.assertEqual(pubsub.NS_PUBSUB, element.items.uri)
            self.assertEqual(0, len(element.items.children))
            self.assertEqual(NS_RSM, element.set.uri)
            self.assertEqual('800', ''.join(element.set.count.children))
            self.assertEqual(None, element.set.first)
            self.assertEqual(None, element.set.last)

        self.resource.items = items
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d
