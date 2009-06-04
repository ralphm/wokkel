# Copyright (c) 2003-2009 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.pubsub}
"""

from zope.interface import verify

from twisted.trial import unittest
from twisted.internet import defer
from twisted.words.xish import domish
from twisted.words.protocols.jabber import error
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import toResponse

from wokkel import data_form, disco, iwokkel, pubsub, shim
from wokkel.generic import parseXml
from wokkel.test.helpers import TestableRequestHandlerMixin, XmlStreamStub

NS_PUBSUB = 'http://jabber.org/protocol/pubsub'
NS_PUBSUB_CONFIG = 'http://jabber.org/protocol/pubsub#node_config'
NS_PUBSUB_ERRORS = 'http://jabber.org/protocol/pubsub#errors'
NS_PUBSUB_EVENT = 'http://jabber.org/protocol/pubsub#event'
NS_PUBSUB_OWNER = 'http://jabber.org/protocol/pubsub#owner'
NS_PUBSUB_META_DATA = 'http://jabber.org/protocol/pubsub#meta-data'

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


    def test_interface(self):
        """
        Do instances of L{pubsub.PubSubClient} provide L{iwokkel.IPubSubClient}?
        """
        verify.verifyObject(iwokkel.IPubSubClient, self.protocol)


    def test_eventItems(self):
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

        def itemsReceived(event):
            self.assertEquals(JID('user@example.org/home'), event.recipient)
            self.assertEquals(JID('pubsub.example.org'), event.sender)
            self.assertEquals('test', event.nodeIdentifier)
            self.assertEquals([item1, item2, item3], event.items)

        d, self.protocol.itemsReceived = calledAsync(itemsReceived)
        self.stub.send(message)
        return d


    def test_eventItemsCollection(self):
        """
        Test receiving an items event resulting in a call to itemsReceived.
        """
        message = domish.Element((None, 'message'))
        message['from'] = 'pubsub.example.org'
        message['to'] = 'user@example.org/home'
        event = message.addElement((NS_PUBSUB_EVENT, 'event'))
        items = event.addElement('items')
        items['node'] = 'test'

        headers = shim.Headers([('Collection', 'collection')])
        message.addChild(headers)

        def itemsReceived(event):
            self.assertEquals(JID('user@example.org/home'), event.recipient)
            self.assertEquals(JID('pubsub.example.org'), event.sender)
            self.assertEquals('test', event.nodeIdentifier)
            self.assertEquals({'Collection': ['collection']}, event.headers)

        d, self.protocol.itemsReceived = calledAsync(itemsReceived)
        self.stub.send(message)
        return d


    def test_eventDelete(self):
        """
        Test receiving a delete event resulting in a call to deleteReceived.
        """
        message = domish.Element((None, 'message'))
        message['from'] = 'pubsub.example.org'
        message['to'] = 'user@example.org/home'
        event = message.addElement((NS_PUBSUB_EVENT, 'event'))
        delete = event.addElement('delete')
        delete['node'] = 'test'

        def deleteReceived(event):
            self.assertEquals(JID('user@example.org/home'), event.recipient)
            self.assertEquals(JID('pubsub.example.org'), event.sender)
            self.assertEquals('test', event.nodeIdentifier)

        d, self.protocol.deleteReceived = calledAsync(deleteReceived)
        self.stub.send(message)
        return d


    def test_eventDeleteRedirect(self):
        """
        Test receiving a delete event with a redirect URI.
        """
        message = domish.Element((None, 'message'))
        message['from'] = 'pubsub.example.org'
        message['to'] = 'user@example.org/home'
        event = message.addElement((NS_PUBSUB_EVENT, 'event'))
        delete = event.addElement('delete')
        delete['node'] = 'test'
        uri = 'xmpp:pubsub.example.org?;node=test2'
        delete.addElement('redirect')['uri'] = uri

        def deleteReceived(event):
            self.assertEquals(JID('user@example.org/home'), event.recipient)
            self.assertEquals(JID('pubsub.example.org'), event.sender)
            self.assertEquals('test', event.nodeIdentifier)
            self.assertEquals(uri, event.redirectURI)

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

        def purgeReceived(event):
            self.assertEquals(JID('user@example.org/home'), event.recipient)
            self.assertEquals(JID('pubsub.example.org'), event.sender)
            self.assertEquals('test', event.nodeIdentifier)

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


    def test_createNodeWithSender(self):
        """
        Test sending create request from a specific JID.
        """

        d = self.protocol.createNode(JID('pubsub.example.org'), 'test',
                                     sender=JID('user@example.org'))

        iq = self.stub.output[-1]
        self.assertEquals('user@example.org', iq['from'])

        response = toResponse(iq, 'result')
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
        self.assertEquals(NS_PUBSUB_OWNER, iq.pubsub.uri)
        children = list(domish.generateElementsQNamed(iq.pubsub.children,
                                                      'delete', NS_PUBSUB_OWNER))
        self.assertEquals(1, len(children))
        child = children[0]
        self.assertEquals('test', child['node'])

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_deleteNodeWithSender(self):
        """
        Test sending delete request.
        """

        d = self.protocol.deleteNode(JID('pubsub.example.org'), 'test',
                                     sender=JID('user@example.org'))

        iq = self.stub.output[-1]
        self.assertEquals('user@example.org', iq['from'])

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


    def test_publishWithSender(self):
        """
        Test sending publish request from a specific JID.
        """

        item = pubsub.Item()
        d = self.protocol.publish(JID('pubsub.example.org'), 'test', [item],
                                  JID('user@example.org'))

        iq = self.stub.output[-1]
        self.assertEquals('user@example.org', iq['from'])

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


    def test_subscribeWithSender(self):
        """
        Test sending subscription request from a specific JID.
        """
        d = self.protocol.subscribe(JID('pubsub.example.org'), 'test',
                                      JID('user@example.org'),
                                      sender=JID('user@example.org'))

        iq = self.stub.output[-1]
        self.assertEquals('user@example.org', iq['from'])

        response = toResponse(iq, 'result')
        pubsub = response.addElement((NS_PUBSUB, 'pubsub'))
        subscription = pubsub.addElement('subscription')
        subscription['node'] = 'test'
        subscription['jid'] = 'user@example.org'
        subscription['subscription'] = 'subscribed'
        self.stub.send(response)
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


    def test_unsubscribeWithSender(self):
        """
        Test sending unsubscription request from a specific JID.
        """
        d = self.protocol.unsubscribe(JID('pubsub.example.org'), 'test',
                                      JID('user@example.org'),
                                      sender=JID('user@example.org'))

        iq = self.stub.output[-1]
        self.assertEquals('user@example.org', iq['from'])
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


    def test_itemsWithSender(self):
        """
        Test sending items request from a specific JID.
        """

        d = self.protocol.items(JID('pubsub.example.org'), 'test',
                               sender=JID('user@example.org'))

        iq = self.stub.output[-1]
        self.assertEquals('user@example.org', iq['from'])

        response = toResponse(iq, 'result')
        items = response.addElement((NS_PUBSUB, 'pubsub')).addElement('items')
        items['node'] = 'test'

        self.stub.send(response)
        return d



class PubSubRequestTest(unittest.TestCase):

    def test_fromElementPublish(self):
        """
        Test parsing a publish request.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <publish node='test'/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('publish', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('test', request.nodeIdentifier)
        self.assertEqual([], request.items)


    def test_fromElementPublishItems(self):
        """
        Test parsing a publish request with items.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <publish node='test'>
              <item id="item1"/>
              <item id="item2"/>
            </publish>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual(2, len(request.items))
        self.assertEqual(u'item1', request.items[0]["id"])
        self.assertEqual(u'item2', request.items[1]["id"])


    def test_fromElementPublishNoNode(self):
        """
        A publish request to the root node should raise an exception.
        """
        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <publish/>
          </pubsub>
        </iq>
        """

        err = self.assertRaises(error.StanzaError,
                                pubsub.PubSubRequest.fromElement,
                                parseXml(xml))
        self.assertEqual('bad-request', err.condition)
        self.assertEqual(NS_PUBSUB_ERRORS, err.appCondition.uri)
        self.assertEqual('nodeid-required', err.appCondition.name)


    def test_fromElementSubscribe(self):
        """
        Test parsing a subscription request.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <subscribe node='test' jid='user@example.org/Home'/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('subscribe', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('test', request.nodeIdentifier)
        self.assertEqual(JID('user@example.org/Home'), request.subscriber)


    def test_fromElementSubscribeEmptyNode(self):
        """
        Test parsing a subscription request to the root node.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <subscribe jid='user@example.org/Home'/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('', request.nodeIdentifier)


    def test_fromElementSubscribeNoJID(self):
        """
        Subscribe requests without a JID should raise a bad-request exception.
        """
        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <subscribe node='test'/>
          </pubsub>
        </iq>
        """
        err = self.assertRaises(error.StanzaError,
                                pubsub.PubSubRequest.fromElement,
                                parseXml(xml))
        self.assertEqual('bad-request', err.condition)
        self.assertEqual(NS_PUBSUB_ERRORS, err.appCondition.uri)
        self.assertEqual('jid-required', err.appCondition.name)

    def test_fromElementUnsubscribe(self):
        """
        Test parsing an unsubscription request.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <unsubscribe node='test' jid='user@example.org/Home'/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('unsubscribe', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('test', request.nodeIdentifier)
        self.assertEqual(JID('user@example.org/Home'), request.subscriber)


    def test_fromElementUnsubscribeNoJID(self):
        """
        Unsubscribe requests without a JID should raise a bad-request exception.
        """
        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <unsubscribe node='test'/>
          </pubsub>
        </iq>
        """
        err = self.assertRaises(error.StanzaError,
                                pubsub.PubSubRequest.fromElement,
                                parseXml(xml))
        self.assertEqual('bad-request', err.condition)
        self.assertEqual(NS_PUBSUB_ERRORS, err.appCondition.uri)
        self.assertEqual('jid-required', err.appCondition.name)


    def test_fromElementOptionsGet(self):
        """
        Test parsing a request for getting subscription options.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <options node='test' jid='user@example.org/Home'/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('optionsGet', request.verb)


    def test_fromElementOptionsSet(self):
        """
        Test parsing a request for setting subscription options.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <options node='test' jid='user@example.org/Home'>
              <x xmlns='jabber:x:data' type='submit'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#subscribe_options</value>
                </field>
                <field var='pubsub#deliver'><value>1</value></field>
              </x>
            </options>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('optionsSet', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('test', request.nodeIdentifier)
        self.assertEqual(JID('user@example.org/Home'), request.subscriber)
        self.assertEqual({'pubsub#deliver': '1'}, request.options)


    def test_fromElementOptionsSetCancel(self):
        """
        Test parsing a request for cancelling setting subscription options.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <options node='test' jid='user@example.org/Home'>
              <x xmlns='jabber:x:data' type='cancel'/>
            </options>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual({}, request.options)


    def test_fromElementOptionsSetBadFormType(self):
        """
        On a options set request unknown fields should be ignored.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <options node='test' jid='user@example.org/Home'>
              <x xmlns='jabber:x:data' type='result'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#node_config</value>
                </field>
                <field var='pubsub#deliver'><value>1</value></field>
              </x>
            </options>
          </pubsub>
        </iq>
        """

        err = self.assertRaises(error.StanzaError,
                                pubsub.PubSubRequest.fromElement,
                                parseXml(xml))
        self.assertEqual('bad-request', err.condition)
        self.assertEqual(None, err.appCondition)


    def test_fromElementOptionsSetNoForm(self):
        """
        On a options set request a form is required.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <options node='test' jid='user@example.org/Home'/>
          </pubsub>
        </iq>
        """
        err = self.assertRaises(error.StanzaError,
                                pubsub.PubSubRequest.fromElement,
                                parseXml(xml))
        self.assertEqual('bad-request', err.condition)
        self.assertEqual(None, err.appCondition)


    def test_fromElementSubscriptions(self):
        """
        Test parsing a request for all subscriptions.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <subscriptions/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('subscriptions', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)


    def test_fromElementAffiliations(self):
        """
        Test parsing a request for all affiliations.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <affiliations/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('affiliations', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)


    def test_fromElementCreate(self):
        """
        Test parsing a request to create a node.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <create node='mynode'/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('create', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('mynode', request.nodeIdentifier)


    def test_fromElementCreateInstant(self):
        """
        Test parsing a request to create an instant node.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <create/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertIdentical(None, request.nodeIdentifier)


    def test_fromElementDefault(self):
        """
        Test parsing a request for the default node configuration.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <default/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('default', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('leaf', request.nodeType)


    def test_fromElementDefaultCollection(self):
        """
        Parsing a request for the default configuration extracts the node type.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <default>
              <x xmlns='jabber:x:data' type='submit'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#node_config</value>
                </field>
                <field var='pubsub#node_type'>
                  <value>collection</value>
                </field>
              </x>
            </default>

          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('collection', request.nodeType)


    def test_fromElementConfigureGet(self):
        """
        Test parsing a node configuration get request.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure node='test'/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('configureGet', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('test', request.nodeIdentifier)


    def test_fromElementConfigureSet(self):
        """
        On a node configuration set request the Data Form is parsed.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure node='test'>
              <x xmlns='jabber:x:data' type='submit'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#node_config</value>
                </field>
                <field var='pubsub#deliver_payloads'><value>0</value></field>
                <field var='pubsub#persist_items'><value>1</value></field>
              </x>
            </configure>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('configureSet', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('test', request.nodeIdentifier)
        self.assertEqual({'pubsub#deliver_payloads': '0',
                          'pubsub#persist_items': '1'}, request.options)


    def test_fromElementConfigureSetCancel(self):
        """
        The node configuration is cancelled, so no options.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure node='test'>
              <x xmlns='jabber:x:data' type='cancel'/>
            </configure>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual({}, request.options)


    def test_fromElementConfigureSetBadFormType(self):
        """
        On a node configuration set request unknown fields should be ignored.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure node='test'>
              <x xmlns='jabber:x:data' type='result'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#node_config</value>
                </field>
                <field var='pubsub#deliver_payloads'><value>0</value></field>
                <field var='x-myfield'><value>1</value></field>
              </x>
            </configure>
          </pubsub>
        </iq>
        """

        err = self.assertRaises(error.StanzaError,
                                pubsub.PubSubRequest.fromElement,
                                parseXml(xml))
        self.assertEqual('bad-request', err.condition)
        self.assertEqual(None, err.appCondition)


    def test_fromElementConfigureSetNoForm(self):
        """
        On a node configuration set request a form is required.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure node='test'/>
          </pubsub>
        </iq>
        """
        err = self.assertRaises(error.StanzaError,
                                pubsub.PubSubRequest.fromElement,
                                parseXml(xml))
        self.assertEqual('bad-request', err.condition)
        self.assertEqual(None, err.appCondition)


    def test_fromElementItems(self):
        """
        Test parsing an items request.
        """
        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <items node='test'/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('items', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('test', request.nodeIdentifier)
        self.assertIdentical(None, request.maxItems)
        self.assertEqual([], request.itemIdentifiers)


    def test_fromElementRetract(self):
        """
        Test parsing a retract request.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <retract node='test'>
              <item id='item1'/>
              <item id='item2'/>
            </retract>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('retract', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('test', request.nodeIdentifier)
        self.assertEqual(['item1', 'item2'], request.itemIdentifiers)


    def test_fromElementPurge(self):
        """
        Test parsing a purge request.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <purge node='test'/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('purge', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('test', request.nodeIdentifier)


    def test_fromElementDelete(self):
        """
        Test parsing a delete request.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <delete node='test'/>
          </pubsub>
        </iq>
        """

        request = pubsub.PubSubRequest.fromElement(parseXml(xml))
        self.assertEqual('delete', request.verb)
        self.assertEqual(JID('user@example.org'), request.sender)
        self.assertEqual(JID('pubsub.example.org'), request.recipient)
        self.assertEqual('test', request.nodeIdentifier)



class PubSubServiceTest(unittest.TestCase, TestableRequestHandlerMixin):
    """
    Tests for L{pubsub.PubSubService}.
    """

    def setUp(self):
        self.stub = XmlStreamStub()
        self.resource = pubsub.PubSubResource()
        self.service = pubsub.PubSubService(self.resource)
        self.service.send = self.stub.xmlstream.send

    def test_interface(self):
        """
        Do instances of L{pubsub.PubSubService} provide L{iwokkel.IPubSubService}?
        """
        verify.verifyObject(iwokkel.IPubSubService, self.service)


    def test_connectionMade(self):
        """
        Verify setup of observers in L{pubsub.connectionMade}.
        """
        requests = []

        def handleRequest(iq):
            requests.append(iq)

        self.service.xmlstream = self.stub.xmlstream
        self.service.handleRequest = handleRequest
        self.service.connectionMade()

        for namespace in (NS_PUBSUB, NS_PUBSUB_OWNER):
            for stanzaType in ('get', 'set'):
                iq = domish.Element((None, 'iq'))
                iq['type'] = stanzaType
                iq.addElement((namespace, 'pubsub'))
                self.stub.xmlstream.dispatch(iq)

        self.assertEqual(4, len(requests))


    def test_getDiscoInfo(self):
        """
        Test getDiscoInfo calls getNodeInfo and returns some minimal info.
        """
        def cb(info):
            discoInfo = disco.DiscoInfo()
            for item in info:
                discoInfo.append(item)
            self.assertIn(('pubsub', 'service'), discoInfo.identities)
            self.assertIn(disco.NS_DISCO_ITEMS, discoInfo.features)

        d = self.service.getDiscoInfo(JID('user@example.org/home'),
                                      JID('pubsub.example.org'), '')
        d.addCallback(cb)
        return d


    def test_getDiscoInfoNodeType(self):
        """
        Test getDiscoInfo with node type.
        """
        def cb(info):
            discoInfo = disco.DiscoInfo()
            for item in info:
                discoInfo.append(item)
            self.assertIn(('pubsub', 'collection'), discoInfo.identities)

        def getInfo(requestor, target, nodeIdentifier):
            return defer.succeed({'type': 'collection',
                                  'meta-data': {}})

        self.resource.getInfo = getInfo
        d = self.service.getDiscoInfo(JID('user@example.org/home'),
                                      JID('pubsub.example.org'), '')
        d.addCallback(cb)
        return d


    def test_getDiscoInfoMetaData(self):
        """
        Test getDiscoInfo with returned meta data.
        """
        def cb(info):
            discoInfo = disco.DiscoInfo()
            for item in info:
                discoInfo.append(item)

            self.assertIn(('pubsub', 'leaf'), discoInfo.identities)
            self.assertIn(NS_PUBSUB_META_DATA, discoInfo.extensions)
            form = discoInfo.extensions[NS_PUBSUB_META_DATA]
            self.assertIn('pubsub#node_type', form.fields)

        def getInfo(requestor, target, nodeIdentifier):
            metaData = [{'var': 'pubsub#persist_items',
                         'label': 'Persist items to storage',
                         'value': True}]
            return defer.succeed({'type': 'leaf', 'meta-data': metaData})

        self.resource.getInfo = getInfo
        d = self.service.getDiscoInfo(JID('user@example.org/home'),
                                      JID('pubsub.example.org'), '')
        d.addCallback(cb)
        return d


    def test_getDiscoInfoResourceFeatures(self):
        """
        Test getDiscoInfo with the resource features.
        """
        def cb(info):
            discoInfo = disco.DiscoInfo()
            for item in info:
                discoInfo.append(item)
            self.assertIn('http://jabber.org/protocol/pubsub#publish',
                          discoInfo.features)

        self.resource.features = ['publish']
        d = self.service.getDiscoInfo(JID('user@example.org/home'),
                                      JID('pubsub.example.org'), '')
        d.addCallback(cb)
        return d


    def test_getDiscoItemsRoot(self):
        """
        Test getDiscoItems on the root node.
        """
        def getNodes(requestor, service, nodeIdentifier):
            return defer.succeed(['node1', 'node2'])

        def cb(items):
            self.assertEqual(2, len(items))
            item1, item2 = items

            self.assertEqual(JID('pubsub.example.org'), item1.entity)
            self.assertEqual('node1', item1.nodeIdentifier)

            self.assertEqual(JID('pubsub.example.org'), item2.entity)
            self.assertEqual('node2', item2.nodeIdentifier)

        self.resource.getNodes = getNodes
        d = self.service.getDiscoItems(JID('user@example.org/home'),
                                       JID('pubsub.example.org'),
                                       '')
        d.addCallback(cb)
        return d


    def test_getDiscoItemsRootHideNodes(self):
        """
        Test getDiscoItems on the root node.
        """
        def getNodes(requestor, service, nodeIdentifier):
            raise Exception("Unexpected call to getNodes")

        def cb(items):
            self.assertEqual([], items)

        self.service.hideNodes = True
        self.resource.getNodes = getNodes
        d = self.service.getDiscoItems(JID('user@example.org/home'),
                                       JID('pubsub.example.org'),
                                       '')
        d.addCallback(cb)
        return d


    def test_getDiscoItemsNonRoot(self):
        """
        Test getDiscoItems on a non-root node.
        """
        def getNodes(requestor, service, nodeIdentifier):
            return defer.succeed(['node1', 'node2'])

        def cb(items):
            self.assertEqual(2, len(items))

        self.resource.getNodes = getNodes
        d = self.service.getDiscoItems(JID('user@example.org/home'),
                                       JID('pubsub.example.org'),
                                       'test')
        d.addCallback(cb)
        return d


    def test_on_publish(self):
        """
        A publish request should result in L{PubSubService.publish} being
        called.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <publish node='test'/>
          </pubsub>
        </iq>
        """

        def publish(request):
            return defer.succeed(None)

        self.resource.publish = publish
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        return self.handleRequest(xml)


    def test_on_subscribe(self):
        """
        A successful subscription should return the current subscription.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <subscribe node='test' jid='user@example.org/Home'/>
          </pubsub>
        </iq>
        """

        def subscribe(request):
            return defer.succeed(pubsub.Subscription(request.nodeIdentifier,
                                                     request.subscriber,
                                                     'subscribed'))

        def cb(element):
            self.assertEqual('pubsub', element.name)
            self.assertEqual(NS_PUBSUB, element.uri)
            subscription = element.subscription
            self.assertEqual(NS_PUBSUB, subscription.uri)
            self.assertEqual('test', subscription['node'])
            self.assertEqual('user@example.org/Home', subscription['jid'])
            self.assertEqual('subscribed', subscription['subscription'])

        self.resource.subscribe = subscribe
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_on_subscribeEmptyNode(self):
        """
        A successful subscription on root node should return no node attribute.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <subscribe jid='user@example.org/Home'/>
          </pubsub>
        </iq>
        """

        def subscribe(request):
            return defer.succeed(pubsub.Subscription(request.nodeIdentifier,
                                                     request.subscriber,
                                                     'subscribed'))

        def cb(element):
            self.assertFalse(element.subscription.hasAttribute('node'))

        self.resource.subscribe = subscribe
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_on_unsubscribe(self):
        """
        A successful unsubscription should return an empty response.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <unsubscribe node='test' jid='user@example.org/Home'/>
          </pubsub>
        </iq>
        """

        def unsubscribe(request):
            return defer.succeed(None)

        def cb(element):
            self.assertIdentical(None, element)

        self.resource.unsubscribe = unsubscribe
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_on_optionsGet(self):
        """
        Getting subscription options is not supported.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <options node='test' jid='user@example.org/Home'/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_on_optionsSet(self):
        """
        Setting subscription options is not supported.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <options node='test' jid='user@example.org/Home'>
              <x xmlns='jabber:x:data' type='submit'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#subscribe_options</value>
                </field>
                <field var='pubsub#deliver'><value>1</value></field>
              </x>
            </options>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_on_subscriptions(self):
        """
        A subscriptions request should result in
        L{PubSubService.subscriptions} being called and the result prepared
        for the response.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <subscriptions/>
          </pubsub>
        </iq>
        """

        def subscriptions(request):
            subscription = pubsub.Subscription('test', JID('user@example.org'),
                                               'subscribed')
            return defer.succeed([subscription])

        def cb(element):
            self.assertEqual('pubsub', element.name)
            self.assertEqual(NS_PUBSUB, element.uri)
            self.assertEqual(NS_PUBSUB, element.subscriptions.uri)
            children = list(element.subscriptions.elements())
            self.assertEqual(1, len(children))
            subscription = children[0]
            self.assertEqual('subscription', subscription.name)
            self.assertEqual(NS_PUBSUB, subscription.uri)
            self.assertEqual('user@example.org', subscription['jid'])
            self.assertEqual('test', subscription['node'])
            self.assertEqual('subscribed', subscription['subscription'])

        self.resource.subscriptions = subscriptions
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_on_affiliations(self):
        """
        A subscriptions request should result in
        L{PubSubService.affiliations} being called and the result prepared
        for the response.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <affiliations/>
          </pubsub>
        </iq>
        """

        def affiliations(request):
            affiliation = ('test', 'owner')
            return defer.succeed([affiliation])

        def cb(element):
            self.assertEqual('pubsub', element.name)
            self.assertEqual(NS_PUBSUB, element.uri)
            self.assertEqual(NS_PUBSUB, element.affiliations.uri)
            children = list(element.affiliations.elements())
            self.assertEqual(1, len(children))
            affiliation = children[0]
            self.assertEqual('affiliation', affiliation.name)
            self.assertEqual(NS_PUBSUB, affiliation.uri)
            self.assertEqual('test', affiliation['node'])
            self.assertEqual('owner', affiliation['affiliation'])

        self.resource.affiliations = affiliations
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_on_create(self):
        """
        Replies to create node requests don't return the created node.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <create node='mynode'/>
          </pubsub>
        </iq>
        """

        def create(request):
            return defer.succeed(request.nodeIdentifier)

        def cb(element):
            self.assertIdentical(None, element)

        self.resource.create = create
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_on_createChanged(self):
        """
        Replies to create node requests return the created node if changed.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <create node='mynode'/>
          </pubsub>
        </iq>
        """

        def create(request):
            return defer.succeed(u'myrenamednode')

        def cb(element):
            self.assertEqual('pubsub', element.name)
            self.assertEqual(NS_PUBSUB, element.uri)
            self.assertEqual(NS_PUBSUB, element.create.uri)
            self.assertEqual(u'myrenamednode',
                             element.create.getAttribute('node'))

        self.resource.create = create
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_on_createInstant(self):
        """
        Replies to create instant node requests return the created node.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <create/>
          </pubsub>
        </iq>
        """

        def create(request):
            return defer.succeed(u'random')

        def cb(element):
            self.assertEqual('pubsub', element.name)
            self.assertEqual(NS_PUBSUB, element.uri)
            self.assertEqual(NS_PUBSUB, element.create.uri)
            self.assertEqual(u'random', element.create.getAttribute('node'))

        self.resource.create = create
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_on_default(self):
        """
        A default request should result in
        L{PubSubService.getDefaultConfiguration} being called.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <default/>
          </pubsub>
        </iq>
        """

        def getConfigurationOptions():
            return {
                "pubsub#persist_items":
                    {"type": "boolean",
                     "label": "Persist items to storage"},
                "pubsub#deliver_payloads":
                    {"type": "boolean",
                     "label": "Deliver payloads with event notifications"}
                }

        def default(request):
            return defer.succeed({})

        def cb(element):
            self.assertEqual('pubsub', element.name)
            self.assertEqual(NS_PUBSUB_OWNER, element.uri)
            self.assertEqual(NS_PUBSUB_OWNER, element.default.uri)
            form = data_form.Form.fromElement(element.default.x)
            self.assertEqual(NS_PUBSUB_CONFIG, form.formNamespace)

        self.resource.getConfigurationOptions = getConfigurationOptions
        self.resource.default = default
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_on_defaultCollection(self):
        """
        Responses to default requests should depend on passed node type.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <default>
              <x xmlns='jabber:x:data' type='submit'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#node_config</value>
                </field>
                <field var='pubsub#node_type'>
                  <value>collection</value>
                </field>
              </x>
            </default>

          </pubsub>
        </iq>
        """

        def getConfigurationOptions():
            return {
                "pubsub#deliver_payloads":
                    {"type": "boolean",
                     "label": "Deliver payloads with event notifications"}
                }

        def default(request):
            return defer.succeed({})

        self.resource.getConfigurationOptions = getConfigurationOptions
        self.resource.default = default
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        return self.handleRequest(xml)


    def test_on_defaultUnknownNodeType(self):
        """
        A default request should result in
        L{PubSubResource.default} being called.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <default>
              <x xmlns='jabber:x:data' type='submit'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#node_config</value>
                </field>
                <field var='pubsub#node_type'>
                  <value>unknown</value>
                </field>
              </x>
            </default>

          </pubsub>
        </iq>
        """

        def default(request):
            self.fail("Unexpected call to getConfiguration")

        def cb(result):
            self.assertEquals('not-acceptable', result.condition)

        self.resource.default = default
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_on_configureGet(self):
        """
        On a node configuration get
        requestL{PubSubResource.configureGet} is called and results in a
        data form with the configuration.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure node='test'/>
          </pubsub>
        </iq>
        """

        def getConfigurationOptions():
            return {
                "pubsub#persist_items":
                    {"type": "boolean",
                     "label": "Persist items to storage"},
                "pubsub#deliver_payloads":
                    {"type": "boolean",
                     "label": "Deliver payloads with event notifications"},
                "pubsub#owner":
                    {"type": "jid-single",
                     "label": "Owner of the node"}
                }

        def configureGet(request):
            return defer.succeed({'pubsub#deliver_payloads': '0',
                                  'pubsub#persist_items': '1',
                                  'pubsub#owner': JID('user@example.org'),
                                  'x-myfield': ['a', 'b']})

        def cb(element):
            self.assertEqual('pubsub', element.name)
            self.assertEqual(NS_PUBSUB_OWNER, element.uri)
            self.assertEqual(NS_PUBSUB_OWNER, element.configure.uri)
            form = data_form.Form.fromElement(element.configure.x)
            self.assertEqual(NS_PUBSUB_CONFIG, form.formNamespace)
            fields = form.fields

            self.assertIn('pubsub#deliver_payloads', fields)
            field = fields['pubsub#deliver_payloads']
            self.assertEqual('boolean', field.fieldType)
            field.typeCheck()
            self.assertEqual(False, field.value)

            self.assertIn('pubsub#persist_items', fields)
            field = fields['pubsub#persist_items']
            self.assertEqual('boolean', field.fieldType)
            field.typeCheck()
            self.assertEqual(True, field.value)

            self.assertIn('pubsub#owner', fields)
            field = fields['pubsub#owner']
            self.assertEqual('jid-single', field.fieldType)
            field.typeCheck()
            self.assertEqual(JID('user@example.org'), field.value)

            self.assertNotIn('x-myfield', fields)

        self.resource.getConfigurationOptions = getConfigurationOptions
        self.resource.configureGet = configureGet
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_on_configureSet(self):
        """
        On a node configuration set request the Data Form is parsed and
        L{PubSubResource.configureSet} is called with the passed options.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure node='test'>
              <x xmlns='jabber:x:data' type='submit'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#node_config</value>
                </field>
                <field var='pubsub#deliver_payloads'><value>0</value></field>
                <field var='pubsub#persist_items'><value>1</value></field>
              </x>
            </configure>
          </pubsub>
        </iq>
        """

        def getConfigurationOptions():
            return {
                "pubsub#persist_items":
                    {"type": "boolean",
                     "label": "Persist items to storage"},
                "pubsub#deliver_payloads":
                    {"type": "boolean",
                     "label": "Deliver payloads with event notifications"}
                }

        def configureSet(request):
            self.assertEqual({'pubsub#deliver_payloads': False,
                              'pubsub#persist_items': True}, request.options)
            return defer.succeed(None)

        self.resource.getConfigurationOptions = getConfigurationOptions
        self.resource.configureSet = configureSet
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        return self.handleRequest(xml)


    def test_on_configureSetCancel(self):
        """
        The node configuration is cancelled,
        L{PubSubResource.configureSet} not called.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure node='test'>
              <x xmlns='jabber:x:data' type='cancel'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#node_config</value>
                </field>
              </x>
            </configure>
          </pubsub>
        </iq>
        """

        def configureSet(request):
            self.fail("Unexpected call to setConfiguration")

        self.resource.configureSet = configureSet
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        return self.handleRequest(xml)


    def test_on_configureSetIgnoreUnknown(self):
        """
        On a node configuration set request unknown fields should be ignored.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure node='test'>
              <x xmlns='jabber:x:data' type='submit'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#node_config</value>
                </field>
                <field var='pubsub#deliver_payloads'><value>0</value></field>
                <field var='x-myfield'><value>1</value></field>
              </x>
            </configure>
          </pubsub>
        </iq>
        """

        def getConfigurationOptions():
            return {
                "pubsub#persist_items":
                    {"type": "boolean",
                     "label": "Persist items to storage"},
                "pubsub#deliver_payloads":
                    {"type": "boolean",
                     "label": "Deliver payloads with event notifications"}
                }

        def configureSet(request):
            self.assertEquals(['pubsub#deliver_payloads'],
                              request.options.keys())

        self.resource.getConfigurationOptions = getConfigurationOptions
        self.resource.configureSet = configureSet
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        return self.handleRequest(xml)


    def test_on_configureSetBadFormType(self):
        """
        On a node configuration set request unknown fields should be ignored.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure node='test'>
              <x xmlns='jabber:x:data' type='result'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#node_config</value>
                </field>
                <field var='pubsub#deliver_payloads'><value>0</value></field>
                <field var='x-myfield'><value>1</value></field>
              </x>
            </configure>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('bad-request', result.condition)

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_on_items(self):
        """
        On a items request, return all items for the given node.
        """
        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <items node='test'/>
          </pubsub>
        </iq>
        """

        def items(request):
            return defer.succeed([pubsub.Item('current')])

        def cb(element):
            self.assertEqual(NS_PUBSUB, element.uri)
            self.assertEqual(NS_PUBSUB, element.items.uri)
            self.assertEqual(1, len(element.items.children))
            item = element.items.children[-1]
            self.assertTrue(domish.IElement.providedBy(item))
            self.assertEqual('item', item.name)
            self.assertEqual(NS_PUBSUB, item.uri)
            self.assertEqual('current', item['id'])

        self.resource.items = items
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_on_retract(self):
        """
        A retract request should result in L{PubSubResource.retract}
        being called.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <retract node='test'>
              <item id='item1'/>
              <item id='item2'/>
            </retract>
          </pubsub>
        </iq>
        """

        def retract(request):
            return defer.succeed(None)

        self.resource.retract = retract
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        return self.handleRequest(xml)


    def test_on_purge(self):
        """
        A purge request should result in L{PubSubResource.purge} being
        called.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <purge node='test'/>
          </pubsub>
        </iq>
        """

        def purge(request):
            return defer.succeed(None)

        self.resource.purge = purge
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        return self.handleRequest(xml)


    def test_on_delete(self):
        """
        A delete request should result in L{PubSubResource.delete} being
        called.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <delete node='test'/>
          </pubsub>
        </iq>
        """

        def delete(request):
            return defer.succeed(None)

        self.resource.delete = delete
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)
        return self.handleRequest(xml)


    def test_notifyDelete(self):
        """
        Subscribers should be sent a delete notification.
        """
        subscriptions = [JID('user@example.org')]
        self.service.notifyDelete(JID('pubsub.example.org'), 'test',
                                  subscriptions)
        message = self.stub.output[-1]

        self.assertEquals('message', message.name)
        self.assertIdentical(None, message.uri)
        self.assertEquals('user@example.org', message['to'])
        self.assertEquals('pubsub.example.org', message['from'])
        self.assertTrue(message.event)
        self.assertEqual(NS_PUBSUB_EVENT, message.event.uri)
        self.assertTrue(message.event.delete)
        self.assertEqual(NS_PUBSUB_EVENT, message.event.delete.uri)
        self.assertTrue(message.event.delete.hasAttribute('node'))
        self.assertEqual('test', message.event.delete['node'])


    def test_notifyDeleteRedirect(self):
        """
        Subscribers should be sent a delete notification with redirect.
        """
        redirectURI = 'xmpp:pubsub.example.org?;node=test2'
        subscriptions = [JID('user@example.org')]
        self.service.notifyDelete(JID('pubsub.example.org'), 'test',
                                  subscriptions, redirectURI)
        message = self.stub.output[-1]

        self.assertEquals('message', message.name)
        self.assertIdentical(None, message.uri)
        self.assertEquals('user@example.org', message['to'])
        self.assertEquals('pubsub.example.org', message['from'])
        self.assertTrue(message.event)
        self.assertEqual(NS_PUBSUB_EVENT, message.event.uri)
        self.assertTrue(message.event.delete)
        self.assertEqual(NS_PUBSUB_EVENT, message.event.delete.uri)
        self.assertTrue(message.event.delete.hasAttribute('node'))
        self.assertEqual('test', message.event.delete['node'])
        self.assertTrue(message.event.delete.redirect)
        self.assertEqual(NS_PUBSUB_EVENT, message.event.delete.redirect.uri)
        self.assertTrue(message.event.delete.redirect.hasAttribute('uri'))
        self.assertEqual(redirectURI, message.event.delete.redirect['uri'])


    def test_on_subscriptionsGet(self):
        """
        Getting subscription options is not supported.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <subscriptions/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('manage-subscriptions',
                              result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_on_subscriptionsSet(self):
        """
        Setting subscription options is not supported.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <subscriptions/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('manage-subscriptions',
                              result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_on_affiliationsGet(self):
        """
        Getting subscription options is not supported.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <affiliations/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('modify-affiliations',
                              result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_on_affiliationsSet(self):
        """
        Setting subscription options is not supported.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <affiliations/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('modify-affiliations',
                              result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d



class PubSubServiceWithoutResourceTest(unittest.TestCase, TestableRequestHandlerMixin):

    def setUp(self):
        self.stub = XmlStreamStub()
        self.service = pubsub.PubSubService()
        self.service.send = self.stub.xmlstream.send


    def test_publish(self):
        """
        Non-overridden L{PubSubService.publish} yields unsupported error.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <publish node='mynode'/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('publish', result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_subscribe(self):
        """
        Non-overridden L{PubSubService.subscribe} yields unsupported error.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <subscribe node='test' jid='user@example.org/Home'/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('subscribe', result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_unsubscribe(self):
        """
        Non-overridden L{PubSubService.unsubscribe} yields unsupported error.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <unsubscribe node='test' jid='user@example.org/Home'/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('subscribe', result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_subscriptions(self):
        """
        Non-overridden L{PubSubService.subscriptions} yields unsupported error.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <subscriptions/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('retrieve-subscriptions',
                              result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_affiliations(self):
        """
        Non-overridden L{PubSubService.affiliations} yields unsupported error.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <affiliations/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('retrieve-affiliations',
                              result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_create(self):
        """
        Non-overridden L{PubSubService.create} yields unsupported error.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <create node='mynode'/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('create-nodes', result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_getDefaultConfiguration(self):
        """
        Non-overridden L{PubSubService.getDefaultConfiguration} yields
        unsupported error.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <default/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('retrieve-default', result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_getConfiguration(self):
        """
        Non-overridden L{PubSubService.getConfiguration} yields unsupported
        error.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('config-node', result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_setConfiguration(self):
        """
        Non-overridden L{PubSubService.setConfiguration} yields unsupported
        error.
        """

        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <configure node='test'>
              <x xmlns='jabber:x:data' type='submit'>
                <field var='FORM_TYPE' type='hidden'>
                  <value>http://jabber.org/protocol/pubsub#node_config</value>
                </field>
                <field var='pubsub#deliver_payloads'><value>0</value></field>
                <field var='pubsub#persist_items'><value>1</value></field>
              </x>
            </configure>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('config-node', result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_items(self):
        """
        Non-overridden L{PubSubService.items} yields unsupported error.
        """
        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <items node='test'/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('retrieve-items', result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_retract(self):
        """
        Non-overridden L{PubSubService.retract} yields unsupported error.
        """
        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <retract node='test'>
              <item id='item1'/>
              <item id='item2'/>
            </retract>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('retract-items', result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_purge(self):
        """
        Non-overridden L{PubSubService.purge} yields unsupported error.
        """
        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <purge node='test'/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('purge-nodes', result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_delete(self):
        """
        Non-overridden L{PubSubService.delete} yields unsupported error.
        """
        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub#owner'>
            <delete node='test'/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('delete-nodes', result.appCondition['feature'])

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d



class PubSubResourceTest(unittest.TestCase):

    def setUp(self):
        self.resource = pubsub.PubSubResource()


    def test_interface(self):
        """
        Do instances of L{pubsub.PubSubResource} provide L{iwokkel.IPubSubResource}?
        """
        verify.verifyObject(iwokkel.IPubSubResource, self.resource)


    def test_getNodes(self):
        """
        Default getNodes returns an empty list.
        """
        def cb(nodes):
            self.assertEquals([], nodes)

        d = self.resource.getNodes(JID('user@example.org/home'),
                                   JID('pubsub.example.org'),
                                   '')
        d.addCallback(cb)
        return d


    def test_publish(self):
        """
        Non-overridden L{PubSubResource.publish} yields unsupported
        error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('publish', result.appCondition['feature'])

        d = self.resource.publish(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_subscribe(self):
        """
        Non-overridden subscriptions yields unsupported error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('subscribe', result.appCondition['feature'])

        d = self.resource.subscribe(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_unsubscribe(self):
        """
        Non-overridden unsubscribe yields unsupported error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('subscribe', result.appCondition['feature'])

        d = self.resource.unsubscribe(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_subscriptions(self):
        """
        Non-overridden subscriptions yields unsupported error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('retrieve-subscriptions',
                              result.appCondition['feature'])

        d = self.resource.subscriptions(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_affiliations(self):
        """
        Non-overridden affiliations yields unsupported error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('retrieve-affiliations',
                              result.appCondition['feature'])

        d = self.resource.affiliations(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_create(self):
        """
        Non-overridden create yields unsupported error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('create-nodes', result.appCondition['feature'])

        d = self.resource.create(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_default(self):
        """
        Non-overridden default yields unsupported error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('retrieve-default',
                              result.appCondition['feature'])

        d = self.resource.default(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_configureGet(self):
        """
        Non-overridden configureGet yields unsupported
        error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('config-node', result.appCondition['feature'])

        d = self.resource.configureGet(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_configureSet(self):
        """
        Non-overridden configureSet yields unsupported error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('config-node', result.appCondition['feature'])

        d = self.resource.configureSet(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_items(self):
        """
        Non-overridden items yields unsupported error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('retrieve-items', result.appCondition['feature'])

        d = self.resource.items(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_retract(self):
        """
        Non-overridden retract yields unsupported error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('retract-items', result.appCondition['feature'])

        d = self.resource.retract(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_purge(self):
        """
        Non-overridden purge yields unsupported error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('purge-nodes', result.appCondition['feature'])

        d = self.resource.purge(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_delete(self):
        """
        Non-overridden delete yields unsupported error.
        """

        def cb(result):
            self.assertEquals('feature-not-implemented', result.condition)
            self.assertEquals('unsupported', result.appCondition.name)
            self.assertEquals(NS_PUBSUB_ERRORS, result.appCondition.uri)
            self.assertEquals('delete-nodes', result.appCondition['feature'])

        d = self.resource.delete(pubsub.PubSubRequest())
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d
