# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.pubsub}
"""

from zope.interface import verify

from twisted.trial import unittest
from twisted.internet import defer
from twisted.words.xish import domish, xpath
from twisted.words.protocols.jabber import error
from twisted.words.protocols.jabber.jid import JID

from wokkel import data_form, iwokkel, pubsub, shim
from wokkel.generic import parseXml
from wokkel.test.helpers import XmlStreamStub

try:
    from twisted.words.protocols.jabber.xmlstream import toResponse
except ImportError:
    from wokkel.compat import toResponse

NS_PUBSUB = 'http://jabber.org/protocol/pubsub'
NS_PUBSUB_CONFIG = 'http://jabber.org/protocol/pubsub#node_config'
NS_PUBSUB_ERRORS = 'http://jabber.org/protocol/pubsub#errors'
NS_PUBSUB_EVENT = 'http://jabber.org/protocol/pubsub#event'
NS_PUBSUB_OWNER = 'http://jabber.org/protocol/pubsub#owner'

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

        def deleteReceived(event):
            self.assertEquals(JID('user@example.org/home'), event.recipient)
            self.assertEquals(JID('pubsub.example.org'), event.sender)
            self.assertEquals('test', event.nodeIdentifier)

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
    """
    Tests for L{pubsub.PubSubService}.
    """

    def setUp(self):
        self.service = pubsub.PubSubService()

    def handleRequest(self, xml):
        """
        Find a handler and call it directly
        """
        handler = None
        iq = parseXml(xml)
        for queryString, method in self.service.iqHandlers.iteritems():
            if xpath.internQuery(queryString).matches(iq):
                handler = getattr(self.service, method)

        if handler:
            d = defer.maybeDeferred(handler, iq)
        else:
            d = defer.fail(NotImplementedError())

        return d


    def test_interface(self):
        """
        Do instances of L{pubsub.PubSubService} provide L{iwokkel.IPubSubService}?
        """
        verify.verifyObject(iwokkel.IPubSubService, self.service)


    def test_onPublishNoNode(self):
        """
        The root node is always a collection, publishing is a bad request.
        """
        xml = """
        <iq type='set' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <publish/>
          </pubsub>
        </iq>
        """

        def cb(result):
            self.assertEquals('bad-request', result.condition)

        d = self.handleRequest(xml)
        self.assertFailure(d, error.StanzaError)
        d.addCallback(cb)
        return d


    def test_onPublish(self):
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

        def publish(requestor, service, nodeIdentifier, items):
            self.assertEqual(JID('user@example.org'), requestor)
            self.assertEqual(JID('pubsub.example.org'), service)
            self.assertEqual('test', nodeIdentifier)
            self.assertEqual([], items)
            return defer.succeed(None)

        self.service.publish = publish
        return self.handleRequest(xml)


    def test_onOptionsGet(self):
        """
        Subscription options are not supported.
        """

        xml = """
        <iq type='get' to='pubsub.example.org'
                       from='user@example.org'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <options/>
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


    def test_onDefault(self):
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

        def getDefaultConfiguration(requestor, service, nodeType):
            self.assertEqual(JID('user@example.org'), requestor)
            self.assertEqual(JID('pubsub.example.org'), service)
            self.assertEqual('leaf', nodeType)
            return defer.succeed({})

        def cb(element):
            self.assertEqual('pubsub', element.name)
            self.assertEqual(NS_PUBSUB_OWNER, element.uri)
            self.assertEqual(NS_PUBSUB_OWNER, element.default.uri)
            form = data_form.Form.fromElement(element.default.x)
            self.assertEqual(NS_PUBSUB_CONFIG, form.formNamespace)

        self.service.getConfigurationOptions = getConfigurationOptions
        self.service.getDefaultConfiguration = getDefaultConfiguration
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_onConfigureGet(self):
        """
        On a node configuration get request L{PubSubService.getConfiguration}
        is called and results in a data form with the configuration.
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
                     "label": "Deliver payloads with event notifications"}
                }

        def getConfiguration(requestor, service, nodeIdentifier):
            self.assertEqual(JID('user@example.org'), requestor)
            self.assertEqual(JID('pubsub.example.org'), service)
            self.assertEqual('test', nodeIdentifier)

            return defer.succeed({'pubsub#deliver_payloads': '0',
                                  'pubsub#persist_items': '1'})

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
            self.assertEqual(False, field.value)

            self.assertIn('pubsub#persist_items', fields)
            field = fields['pubsub#persist_items']
            self.assertEqual('boolean', field.fieldType)
            self.assertEqual(True, field.value)

        self.service.getConfigurationOptions = getConfigurationOptions
        self.service.getConfiguration = getConfiguration
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_onConfigureSet(self):
        """
        On a node configuration set request the Data Form is parsed and
        L{PubSubService.setConfiguration} is called with the passed options.
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

        def setConfiguration(requestor, service, nodeIdentifier, options):
            self.assertEqual(JID('user@example.org'), requestor)
            self.assertEqual(JID('pubsub.example.org'), service)
            self.assertEqual('test', nodeIdentifier)
            self.assertEqual({'pubsub#deliver_payloads': False,
                              'pubsub#persist_items': True}, options)
            return defer.succeed(None)

        self.service.getConfigurationOptions = getConfigurationOptions
        self.service.setConfiguration = setConfiguration
        return self.handleRequest(xml)


    def test_onConfigureSetCancel(self):
        """
        The node configuration is cancelled, L{PubSubService.setConfiguration}
        not called.
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

        def setConfiguration(requestor, service, nodeIdentifier, options):
            self.fail("Unexpected call to setConfiguration")

        self.service.setConfiguration = setConfiguration
        return self.handleRequest(xml)


    def test_onConfigureSetIgnoreUnknown(self):
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

        def setConfiguration(requestor, service, nodeIdentifier, options):
            self.assertEquals(['pubsub#deliver_payloads'], options.keys())

        self.service.getConfigurationOptions = getConfigurationOptions
        self.service.setConfiguration = setConfiguration
        return self.handleRequest(xml)


    def test_onItems(self):
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

        def items(requestor, service, nodeIdentifier, maxItems, items):
            self.assertEqual(JID('user@example.org'), requestor)
            self.assertEqual(JID('pubsub.example.org'), service)
            self.assertEqual('test', nodeIdentifier)
            self.assertIdentical(None, maxItems)
            self.assertEqual([], items)
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

        self.service.items = items
        d = self.handleRequest(xml)
        d.addCallback(cb)
        return d


    def test_onRetract(self):
        """
        A retract request should result in L{PubSubService.retract} being
        called.
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

        def retract(requestor, service, nodeIdentifier, itemIdentifiers):
            self.assertEqual(JID('user@example.org'), requestor)
            self.assertEqual(JID('pubsub.example.org'), service)
            self.assertEqual('test', nodeIdentifier)
            self.assertEqual(['item1', 'item2'], itemIdentifiers)
            return defer.succeed(None)

        self.service.retract = retract
        return self.handleRequest(xml)


    def test_onPurge(self):
        """
        A purge request should result in L{PubSubService.purge} being
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

        def purge(requestor, service, nodeIdentifier):
            self.assertEqual(JID('user@example.org'), requestor)
            self.assertEqual(JID('pubsub.example.org'), service)
            self.assertEqual('test', nodeIdentifier)
            return defer.succeed(None)

        self.service.purge = purge
        return self.handleRequest(xml)


    def test_onDelete(self):
        """
        A delete request should result in L{PubSubService.delete} being
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

        def delete(requestor, service, nodeIdentifier):
            self.assertEqual(JID('user@example.org'), requestor)
            self.assertEqual(JID('pubsub.example.org'), service)
            self.assertEqual('test', nodeIdentifier)
            return defer.succeed(None)

        self.service.delete = delete
        return self.handleRequest(xml)
