# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.pubsub}
"""

from twisted.trial import unittest
from twisted.internet import defer
from twisted.words.xish import domish
from twisted.words.protocols.jabber import error
from twisted.words.protocols.jabber.jid import JID

from wokkel import pubsub
from wokkel.test.helpers import XmlStreamStub

try:
    from twisted.words.protocols.jabber.xmlstream import toResponse
except ImportError:
    from wokkel.compat import toResponse

NS_PUBSUB = 'http://jabber.org/protocol/pubsub'
NS_PUBSUB_ERRORS = 'http://jabber.org/protocol/pubsub#errors'
NS_PUBSUB_EVENT = 'http://jabber.org/protocol/pubsub#event'

def calledAsync(fn):
    """
    Function wrapper that fires a deferred upon calling the given function.
    """
    d = defer.Deferred()

    def func(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
        except:
            d.errback()
        else:
            d.callback(result)

    return d, func


class PubSubClientTest(unittest.TestCase):
    timeout = 2

    def setUp(self):
        self.stub = XmlStreamStub()
        self.protocol = pubsub.PubSubClient()
        self.protocol.xmlstream = self.stub.xmlstream
        self.protocol.connectionInitialized()


    def test_event_items(self):
        """
        Test receiving an items event resulting in a call to itemsReceived.
        """
        message = domish.Element((None, 'message'))
        message['from'] = 'pubsub.example.org'
        message['to'] = 'user@example.org/home'
        event = message.addElement((NS_PUBSUB_EVENT, 'event'))
        items = event.addElement('items')
        items['node'] = 'test'
        item1 = items.addElement('item')
        item1['id'] = 'item1'
        item2 = items.addElement('retract')
        item2['id'] = 'item2'
        item3 = items.addElement('item')
        item3['id'] = 'item3'

        def itemsReceived(recipient, service, nodeIdentifier, items):
            self.assertEquals(JID('user@example.org/home'), recipient)
            self.assertEquals(JID('pubsub.example.org'), service)
            self.assertEquals('test', nodeIdentifier)
            self.assertEquals([item1, item2, item3], items)

        d, self.protocol.itemsReceived = calledAsync(itemsReceived)
        self.stub.send(message)
        return d


    def test_event_delete(self):
        """
        Test receiving a delete event resulting in a call to deleteReceived.
        """
        message = domish.Element((None, 'message'))
        message['from'] = 'pubsub.example.org'
        message['to'] = 'user@example.org/home'
        event = message.addElement((NS_PUBSUB_EVENT, 'event'))
        items = event.addElement('delete')
        items['node'] = 'test'

        def deleteReceived(recipient, service, nodeIdentifier):
            self.assertEquals(JID('user@example.org/home'), recipient)
            self.assertEquals(JID('pubsub.example.org'), service)
            self.assertEquals('test', nodeIdentifier)

        d, self.protocol.deleteReceived = calledAsync(deleteReceived)
        self.stub.send(message)
        return d


    def test_event_purge(self):
        """
        Test receiving a purge event resulting in a call to purgeReceived.
        """
        message = domish.Element((None, 'message'))
        message['from'] = 'pubsub.example.org'
        message['to'] = 'user@example.org/home'
        event = message.addElement((NS_PUBSUB_EVENT, 'event'))
        items = event.addElement('purge')
        items['node'] = 'test'

        def purgeReceived(recipient, service, nodeIdentifier):
            self.assertEquals(JID('user@example.org/home'), recipient)
            self.assertEquals(JID('pubsub.example.org'), service)
            self.assertEquals('test', nodeIdentifier)

        d, self.protocol.purgeReceived = calledAsync(purgeReceived)
        self.stub.send(message)
        return d


    def test_createNode(self):
        """
        Test sending create request.
        """

        def cb(nodeIdentifier):
            self.assertEquals('test', nodeIdentifier)

        d = self.protocol.createNode(JID('pubsub.example.org'), 'test')
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('set', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'create', NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_createNodeInstant(self):
        """
        Test sending create request resulting in an instant node.
        """

        def cb(nodeIdentifier):
            self.assertEquals('test', nodeIdentifier)

        d = self.protocol.createNode(JID('pubsub.example.org'))
        d.addCallback(cb)

        iq = self.stub.output[-1]
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'create', NS_PUBSUB))
        child = children[0]
        self.assertFalse(child.hasAttribute('node'))

        response = toResponse(iq, 'result')
        command = response.addElement((NS_PUBSUB, 'pubsub'))
        create = command.addElement('create')
        create['node'] = 'test'
        self.stub.send(response)
        return d


    def test_createNodeRenamed(self):
        """
        Test sending create request resulting in renamed node.
        """

        def cb(nodeIdentifier):
            self.assertEquals('test2', nodeIdentifier)

        d = self.protocol.createNode(JID('pubsub.example.org'), 'test')
        d.addCallback(cb)

        iq = self.stub.output[-1]
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'create', NS_PUBSUB))
        child = children[0]
        self.assertEquals('test', child['node'])

        response = toResponse(iq, 'result')
        command = response.addElement((NS_PUBSUB, 'pubsub'))
        create = command.addElement('create')
        create['node'] = 'test2'
        self.stub.send(response)
        return d


    def test_deleteNode(self):
        """
        Test sending delete request.
        """

        d = self.protocol.deleteNode(JID('pubsub.example.org'), 'test')

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('set', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'delete', NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_publish(self):
        """
        Test sending publish request.
        """

        item = pubsub.Item()
        d = self.protocol.publish(JID('pubsub.example.org'), 'test', [item])

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('set', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'publish', NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])
        items = list(domish.generateElementsQNamed(child.children,
                                                   'item', NS_PUBSUB))
        self.assertEquals(1, len(items))
        self.assertIdentical(item, items[0])

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_publishNoItems(self):
        """
        Test sending publish request without items.
        """

        d = self.protocol.publish(JID('pubsub.example.org'), 'test')

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('set', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'publish', NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_subscribe(self):
        """
        Test sending subscription request.
        """
        d = self.protocol.subscribe(JID('pubsub.example.org'), 'test',
                                      JID('user@example.org'))

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('set', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'subscribe', NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])
        self.assertEquals('user@example.org', child['jid'])

        response = toResponse(iq, 'result')
        pubsub = response.addElement((NS_PUBSUB, 'pubsub'))
        subscription = pubsub.addElement('subscription')
        subscription['node'] = 'test'
        subscription['jid'] = 'user@example.org'
        subscription['subscription'] = 'subscribed'
        self.stub.send(response)
        return d


    def test_subscribePending(self):
        """
        Test sending subscription request that results in a pending
        subscription.
        """
        d = self.protocol.subscribe(JID('pubsub.example.org'), 'test',
                                      JID('user@example.org'))

        iq = self.stub.output[-1]
        response = toResponse(iq, 'result')
        command = response.addElement((NS_PUBSUB, 'pubsub'))
        subscription = command.addElement('subscription')
        subscription['node'] = 'test'
        subscription['jid'] = 'user@example.org'
        subscription['subscription'] = 'pending'
        self.stub.send(response)
        self.assertFailure(d, pubsub.SubscriptionPending)
        return d


    def test_subscribeUnconfigured(self):
        """
        Test sending subscription request that results in an unconfigured
        subscription.
        """
        d = self.protocol.subscribe(JID('pubsub.example.org'), 'test',
                                      JID('user@example.org'))

        iq = self.stub.output[-1]
        response = toResponse(iq, 'result')
        command = response.addElement((NS_PUBSUB, 'pubsub'))
        subscription = command.addElement('subscription')
        subscription['node'] = 'test'
        subscription['jid'] = 'user@example.org'
        subscription['subscription'] = 'unconfigured'
        self.stub.send(response)
        self.assertFailure(d, pubsub.SubscriptionUnconfigured)
        return d


    def test_unsubscribe(self):
        """
        Test sending unsubscription request.
        """
        d = self.protocol.unsubscribe(JID('pubsub.example.org'), 'test',
                                      JID('user@example.org'))

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('set', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'unsubscribe', NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])
        self.assertEquals('user@example.org', child['jid'])

        self.stub.send(toResponse(iq, 'result'))
        return d


    def test_items(self):
        """
        Test sending items request.
        """
        def cb(items):
            self.assertEquals([], items)

        d = self.protocol.items(JID('pubsub.example.org'), 'test')
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('get', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'items', NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])

        response = toResponse(iq, 'result')
        items = response.addElement((NS_PUBSUB, 'pubsub')).addElement('items')
        items['node'] = 'test'

        self.stub.send(response)

        return d


    def test_itemsMaxItems(self):
        """
        Test sending items request, with limit on the number of items.
        """
        def cb(items):
            self.assertEquals(2, len(items))
            self.assertEquals([item1, item2], items)

        d = self.protocol.items(JID('pubsub.example.org'), 'test', maxItems=2)
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('pubsub.example.org', iq.getAttribute('to'))
        self.assertEquals('get', iq.getAttribute('type'))
        self.assertEquals('pubsub', iq.pubsub.name)
        self.assertEquals(NS_PUBSUB, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'items', NS_PUBSUB))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])
        self.assertEquals('2', child['max_items'])

        response = toResponse(iq, 'result')
        items = response.addElement((NS_PUBSUB, 'pubsub')).addElement('items')
        items['node'] = 'test'
        item1 = items.addElement('item')
        item1['id'] = 'item1'
        item2 = items.addElement('item')
        item2['id'] = 'item2'

        self.stub.send(response)

        return d



class PubSubServiceTest(unittest.TestCase):

    def setUp(self):
        self.output = []

    def send(self, obj):
        self.output.append(obj)

    def test_onPublishNoNode(self):
        handler = pubsub.PubSubService()
        handler.parent = self
        iq = domish.Element((None, 'iq'))
        iq['from'] = 'user@example.org'
        iq['to'] = 'pubsub.example.org'
        iq['type'] = 'set'
        iq.addElement((NS_PUBSUB, 'pubsub'))
        iq.pubsub.addElement('publish')
        handler.handleRequest(iq)

        e = error.exceptionFromStanza(self.output[-1])
        self.assertEquals('bad-request', e.condition)

    def test_onPublish(self):
        class Handler(pubsub.PubSubService):
            def publish(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        handler = Handler()
        handler.parent = self
        iq = domish.Element((None, 'iq'))
        iq['type'] = 'set'
        iq['from'] = 'user@example.org'
        iq['to'] = 'pubsub.example.org'
        iq.addElement((NS_PUBSUB, 'pubsub'))
        iq.pubsub.addElement('publish')
        iq.pubsub.publish['node'] = 'test'
        handler.handleRequest(iq)

        self.assertEqual((JID('user@example.org'),
                          JID('pubsub.example.org'), 'test', []), handler.args)

    def test_onOptionsGet(self):
        handler = pubsub.PubSubService()
        handler.parent = self
        iq = domish.Element((None, 'iq'))
        iq['from'] = 'user@example.org'
        iq['to'] = 'pubsub.example.org'
        iq['type'] = 'get'
        iq.addElement((NS_PUBSUB, 'pubsub'))
        iq.pubsub.addElement('options')
        handler.handleRequest(iq)

        e = error.exceptionFromStanza(self.output[-1])
        self.assertEquals('feature-not-implemented', e.condition)
        self.assertEquals('unsupported', e.appCondition.name)
        self.assertEquals(NS_PUBSUB_ERRORS, e.appCondition.uri)
