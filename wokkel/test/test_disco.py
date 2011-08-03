# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.disco}.
"""

from zope.interface import implements

from twisted.internet import defer
from twisted.trial import unittest
from twisted.words.protocols.jabber.error import StanzaError
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import toResponse
from twisted.words.xish import domish, utility

from wokkel import data_form, disco
from wokkel.generic import parseXml
from wokkel.subprotocols import XMPPHandler
from wokkel.test.helpers import TestableRequestHandlerMixin, XmlStreamStub

NS_DISCO_INFO = 'http://jabber.org/protocol/disco#info'
NS_DISCO_ITEMS = 'http://jabber.org/protocol/disco#items'

class DiscoFeatureTest(unittest.TestCase):
    """
    Tests for L{disco.DiscoFeature}.
    """

    def test_init(self):
        """
        Test initialization with a with feature namespace URI.
        """
        feature = disco.DiscoFeature(u'testns')
        self.assertEqual(u'testns', feature)


    def test_toElement(self):
        """
        Test proper rendering to a DOM representation.

        The returned element should be properly named and have a C{var}
        attribute that holds the feature namespace URI.
        """
        feature = disco.DiscoFeature(u'testns')
        element = feature.toElement()
        self.assertEqual(NS_DISCO_INFO, element.uri)
        self.assertEqual(u'feature', element.name)
        self.assertTrue(element.hasAttribute(u'var'))
        self.assertEqual(u'testns', element[u'var'])


    def test_fromElement(self):
        """
        Test creating L{disco.DiscoFeature} from L{domish.Element}.
        """
        element = domish.Element((NS_DISCO_INFO, u'feature'))
        element['var'] = u'testns'
        feature = disco.DiscoFeature.fromElement(element)
        self.assertEqual(u'testns', feature)



class DiscoIdentityTest(unittest.TestCase):
    """
    Tests for L{disco.DiscoIdentity}.
    """

    def test_init(self):
        """
        Test initialization with a category, type and name.
        """
        identity = disco.DiscoIdentity(u'conference', u'text', u'The chatroom')
        self.assertEqual(u'conference', identity.category)
        self.assertEqual(u'text', identity.type)
        self.assertEqual(u'The chatroom', identity.name)


    def test_toElement(self):
        """
        Test proper rendering to a DOM representation.

        The returned element should be properly named and have C{conference},
        C{type}, and C{name} attributes.
        """
        identity = disco.DiscoIdentity(u'conference', u'text', u'The chatroom')
        element = identity.toElement()
        self.assertEqual(NS_DISCO_INFO, element.uri)
        self.assertEqual(u'identity', element.name)
        self.assertEqual(u'conference', element.getAttribute(u'category'))
        self.assertEqual(u'text', element.getAttribute(u'type'))
        self.assertEqual(u'The chatroom', element.getAttribute(u'name'))


    def test_toElementWithoutName(self):
        """
        Test proper rendering to a DOM representation without a name.

        The returned element should be properly named and have C{conference},
        C{type} attributes, no C{name} attribute.
        """
        identity = disco.DiscoIdentity(u'conference', u'text')
        element = identity.toElement()
        self.assertEqual(NS_DISCO_INFO, element.uri)
        self.assertEqual(u'identity', element.name)
        self.assertEqual(u'conference', element.getAttribute(u'category'))
        self.assertEqual(u'text', element.getAttribute(u'type'))
        self.assertFalse(element.hasAttribute(u'name'))


    def test_fromElement(self):
        """
        Test creating L{disco.DiscoIdentity} from L{domish.Element}.
        """
        element = domish.Element((NS_DISCO_INFO, u'identity'))
        element['category'] = u'conference'
        element['type'] = u'text'
        element['name'] = u'The chatroom'
        identity = disco.DiscoIdentity.fromElement(element)
        self.assertEqual(u'conference', identity.category)
        self.assertEqual(u'text', identity.type)
        self.assertEqual(u'The chatroom', identity.name)


    def test_fromElementWithoutName(self):
        """
        Test creating L{disco.DiscoIdentity} from L{domish.Element}, no name.
        """
        element = domish.Element((NS_DISCO_INFO, u'identity'))
        element['category'] = u'conference'
        element['type'] = u'text'
        identity = disco.DiscoIdentity.fromElement(element)
        self.assertEqual(u'conference', identity.category)
        self.assertEqual(u'text', identity.type)
        self.assertEqual(None, identity.name)



class DiscoInfoTest(unittest.TestCase):
    """
    Tests for L{disco.DiscoInfo}.
    """

    def test_toElement(self):
        """
        Test C{toElement} creates a correctly namespaced element, no node.
        """
        info = disco.DiscoInfo()
        element = info.toElement()

        self.assertEqual(NS_DISCO_INFO, element.uri)
        self.assertEqual(u'query', element.name)
        self.assertFalse(element.hasAttribute(u'node'))


    def test_toElementNode(self):
        """
        Test C{toElement} with a node.
        """
        info = disco.DiscoInfo()
        info.nodeIdentifier = u'test'
        element = info.toElement()

        self.assertEqual(u'test', element.getAttribute(u'node'))


    def test_toElementChildren(self):
        """
        Test C{toElement} creates a DOM with proper childs.
        """
        info = disco.DiscoInfo()
        info.append(disco.DiscoFeature(u'jabber:iq:register'))
        info.append(disco.DiscoIdentity(u'conference', u'text'))
        info.append(data_form.Form(u'result'))
        element = info.toElement()

        featureElements = domish.generateElementsQNamed(element.children,
                                                        u'feature',
                                                        NS_DISCO_INFO)
        self.assertEqual(1, len(list(featureElements)))

        identityElements = domish.generateElementsQNamed(element.children,
                                                         u'identity',
                                                         NS_DISCO_INFO)
        self.assertEqual(1, len(list(identityElements)))

        extensionElements = domish.generateElementsQNamed(element.children,
                                                         u'x',
                                                         data_form.NS_X_DATA)
        self.assertEqual(1, len(list(extensionElements)))


    def test_fromElement(self):
        """
        Test properties when creating L{disco.DiscoInfo} from L{domish.Element}.
        """
        xml = """<query xmlns='http://jabber.org/protocol/disco#info'>
                   <identity category='conference'
                             type='text'
                             name='A Dark Cave'/>
                   <feature var='http://jabber.org/protocol/muc'/>
                   <feature var='jabber:iq:register'/>
                   <x xmlns='jabber:x:data' type='result'>
                     <field var='FORM_TYPE' type='hidden'>
                       <value>http://jabber.org/protocol/muc#roominfo</value>
                     </field>
                   </x>
                 </query>"""

        element = parseXml(xml)
        info = disco.DiscoInfo.fromElement(element)

        self.assertIn(u'http://jabber.org/protocol/muc', info.features)
        self.assertIn(u'jabber:iq:register', info.features)

        self.assertIn((u'conference', u'text'), info.identities)
        self.assertEqual(u'A Dark Cave',
                          info.identities[(u'conference', u'text')])

        self.assertIn(u'http://jabber.org/protocol/muc#roominfo',
                      info.extensions)


    def test_fromElementItems(self):
        """
        Test items when creating L{disco.DiscoInfo} from L{domish.Element}.
        """
        xml = """<query xmlns='http://jabber.org/protocol/disco#info'>
                   <identity category='conference'
                             type='text'
                             name='A Dark Cave'/>
                   <feature var='http://jabber.org/protocol/muc'/>
                   <feature var='jabber:iq:register'/>
                   <x xmlns='jabber:x:data' type='result'>
                     <field var='FORM_TYPE' type='hidden'>
                       <value>http://jabber.org/protocol/muc#roominfo</value>
                     </field>
                   </x>
                 </query>"""

        element = parseXml(xml)
        info = disco.DiscoInfo.fromElement(element)

        info = list(info)
        self.assertEqual(4, len(info))

        identity = info[0]
        self.assertEqual(u'conference', identity.category)

        self.assertEqual(u'http://jabber.org/protocol/muc', info[1])
        self.assertEqual(u'jabber:iq:register', info[2])

        extension = info[3]
        self.assertEqual(u'http://jabber.org/protocol/muc#roominfo',
                         extension.formNamespace)


    def test_fromElementNoNode(self):
        """
        Test creating L{disco.DiscoInfo} from L{domish.Element}, no node.
        """
        xml = """<query xmlns='http://jabber.org/protocol/disco#info'/>"""

        element = parseXml(xml)
        info = disco.DiscoInfo.fromElement(element)

        self.assertEqual(u'', info.nodeIdentifier)


    def test_fromElementNode(self):
        """
        Test creating L{disco.DiscoInfo} from L{domish.Element}, with node.
        """
        xml = """<query xmlns='http://jabber.org/protocol/disco#info'
                        node='test'>
                 </query>"""

        element = parseXml(xml)
        info = disco.DiscoInfo.fromElement(element)

        self.assertEqual(u'test', info.nodeIdentifier)



class DiscoItemTest(unittest.TestCase):
    """
    Tests for L{disco.DiscoItem}.
    """

    def test_init(self):
        """
        Test initialization with a category, type and name.
        """
        item = disco.DiscoItem(JID(u'example.org'), u'test', u'The node')
        self.assertEqual(JID(u'example.org'), item.entity)
        self.assertEqual(u'test', item.nodeIdentifier)
        self.assertEqual(u'The node', item.name)


    def test_toElement(self):
        """
        Test proper rendering to a DOM representation.

        The returned element should be properly named and have C{jid}, C{node},
        and C{name} attributes.
        """
        item = disco.DiscoItem(JID(u'example.org'), u'test', u'The node')
        element = item.toElement()
        self.assertEqual(NS_DISCO_ITEMS, element.uri)
        self.assertEqual(u'item', element.name)
        self.assertEqual(u'example.org', element.getAttribute(u'jid'))
        self.assertEqual(u'test', element.getAttribute(u'node'))
        self.assertEqual(u'The node', element.getAttribute(u'name'))


    def test_toElementWithoutName(self):
        """
        Test proper rendering to a DOM representation without a name.

        The returned element should be properly named and have C{jid}, C{node}
        attributes, no C{name} attribute.
        """
        item = disco.DiscoItem(JID(u'example.org'), u'test')
        element = item.toElement()
        self.assertEqual(NS_DISCO_ITEMS, element.uri)
        self.assertEqual(u'item', element.name)
        self.assertEqual(u'example.org', element.getAttribute(u'jid'))
        self.assertEqual(u'test', element.getAttribute(u'node'))
        self.assertFalse(element.hasAttribute(u'name'))


    def test_fromElement(self):
        """
        Test creating L{disco.DiscoItem} from L{domish.Element}.
        """
        element = domish.Element((NS_DISCO_ITEMS, u'item'))
        element[u'jid'] = u'example.org'
        element[u'node'] = u'test'
        element[u'name'] = u'The node'
        item = disco.DiscoItem.fromElement(element)
        self.assertEqual(JID(u'example.org'), item.entity)
        self.assertEqual(u'test', item.nodeIdentifier)
        self.assertEqual(u'The node', item.name)

    def test_fromElementNoNode(self):
        """
        Test creating L{disco.DiscoItem} from L{domish.Element}, no node.
        """
        element = domish.Element((NS_DISCO_ITEMS, u'item'))
        element[u'jid'] = u'example.org'
        element[u'name'] = u'The node'
        item = disco.DiscoItem.fromElement(element)
        self.assertEqual(JID(u'example.org'), item.entity)
        self.assertEqual(u'', item.nodeIdentifier)
        self.assertEqual(u'The node', item.name)


    def test_fromElementNoName(self):
        """
        Test creating L{disco.DiscoItem} from L{domish.Element}, no name.
        """
        element = domish.Element((NS_DISCO_ITEMS, u'item'))
        element[u'jid'] = u'example.org'
        element[u'node'] = u'test'
        item = disco.DiscoItem.fromElement(element)
        self.assertEqual(JID(u'example.org'), item.entity)
        self.assertEqual(u'test', item.nodeIdentifier)
        self.assertEqual(None, item.name)

    def test_fromElementBadJID(self):
        """
        Test creating L{disco.DiscoItem} from L{domish.Element}, bad JID.
        """
        element = domish.Element((NS_DISCO_ITEMS, u'item'))
        element[u'jid'] = u'ex@@@ample.org'
        item = disco.DiscoItem.fromElement(element)
        self.assertIdentical(None, item.entity)



class DiscoItemsTest(unittest.TestCase):
    """
    Tests for L{disco.DiscoItems}.
    """

    def test_toElement(self):
        """
        Test C{toElement} creates a correctly namespaced element, no node.
        """
        items = disco.DiscoItems()
        element = items.toElement()

        self.assertEqual(NS_DISCO_ITEMS, element.uri)
        self.assertEqual(u'query', element.name)
        self.assertFalse(element.hasAttribute(u'node'))


    def test_toElementNode(self):
        """
        Test C{toElement} with a node.
        """
        items = disco.DiscoItems()
        items.nodeIdentifier = u'test'
        element = items.toElement()

        self.assertEqual(u'test', element.getAttribute(u'node'))


    def test_toElementChildren(self):
        """
        Test C{toElement} creates a DOM with proper childs.
        """
        items = disco.DiscoItems()
        items.append(disco.DiscoItem(JID(u'example.org'), u'test', u'A node'))
        element = items.toElement()

        itemElements = domish.generateElementsQNamed(element.children,
                                                     u'item',
                                                     NS_DISCO_ITEMS)
        self.assertEqual(1, len(list(itemElements)))


    def test_fromElement(self):
        """
        Test creating L{disco.DiscoItems} from L{domish.Element}.
        """
        xml = """<query xmlns='http://jabber.org/protocol/disco#items'>
                   <item jid='example.org' node='test' name='A node'/>
                 </query>"""

        element = parseXml(xml)
        items = disco.DiscoItems.fromElement(element)

        items = list(items)
        self.assertEqual(1, len(items))
        item = items[0]

        self.assertEqual(JID(u'example.org'), item.entity)
        self.assertEqual(u'test', item.nodeIdentifier)
        self.assertEqual(u'A node', item.name)


    def test_fromElementNoNode(self):
        """
        Test creating L{disco.DiscoItems} from L{domish.Element}, no node.
        """
        xml = """<query xmlns='http://jabber.org/protocol/disco#items'/>"""

        element = parseXml(xml)
        items = disco.DiscoItems.fromElement(element)

        self.assertEqual(u'', items.nodeIdentifier)


    def test_fromElementNode(self):
        """
        Test creating L{disco.DiscoItems} from L{domish.Element}, with node.
        """
        xml = """<query xmlns='http://jabber.org/protocol/disco#items'
                        node='test'>
                 </query>"""

        element = parseXml(xml)
        items = disco.DiscoItems.fromElement(element)

        self.assertEqual(u'test', items.nodeIdentifier)



class DiscoClientProtocolTest(unittest.TestCase):
    """
    Tests for L{disco.DiscoClientProtocol}.
    """

    def setUp(self):
        """
        Set up stub and protocol for testing.
        """
        self.stub = XmlStreamStub()
        self.patch(XMPPHandler, 'request', self.request)
        self.protocol = disco.DiscoClientProtocol()


    def request(self, request):
        element = request.toElement()
        self.stub.xmlstream.send(element)
        return defer.Deferred()


    def test_requestItems(self):
        """
        Test request sent out by C{requestItems} and parsing of response.
        """
        def cb(items):
            items = list(items)
            self.assertEqual(2, len(items))
            self.assertEqual(JID(u'test.example.org'), items[0].entity)

        d = self.protocol.requestItems(JID(u'example.org'),u"foo")
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEqual(u'example.org', iq.getAttribute(u'to'))
        self.assertEqual(u'get', iq.getAttribute(u'type'))
        self.assertEqual(u'foo', iq.query.getAttribute(u'node'))
        self.assertEqual(NS_DISCO_ITEMS, iq.query.uri)

        response = toResponse(iq, u'result')
        query = response.addElement((NS_DISCO_ITEMS, u'query'))

        element = query.addElement(u'item')
        element[u'jid'] = u'test.example.org'
        element[u'node'] = u'music'
        element[u'name'] = u'Music from the time of Shakespeare'

        element = query.addElement(u'item')
        element[u'jid'] = u"test2.example.org"

        d.callback(response)
        return d


    def test_requestItemsFrom(self):
        """
        A disco items request can be sent with an explicit sender address.
        """
        d = self.protocol.requestItems(JID(u'example.org'),
                                       sender=JID(u'test.example.org'))

        iq = self.stub.output[-1]
        self.assertEqual(u'test.example.org', iq.getAttribute(u'from'))

        response = toResponse(iq, u'result')
        response.addElement((NS_DISCO_ITEMS, u'query'))

        d.callback(response)
        return d


    def test_requestInfo(self):
        """
        Test request sent out by C{requestInfo} and parsing of response.
        """
        def cb(info):
            self.assertIn((u'conference', u'text'), info.identities)
            self.assertIn(u'http://jabber.org/protocol/disco#info',
                          info.features)
            self.assertIn(u'http://jabber.org/protocol/muc',
                          info.features)

        d = self.protocol.requestInfo(JID(u'example.org'),'foo')
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEqual(u'example.org', iq.getAttribute(u'to'))
        self.assertEqual(u'get', iq.getAttribute(u'type'))
        self.assertEqual(u'foo', iq.query.getAttribute(u'node'))
        self.assertEqual(NS_DISCO_INFO, iq.query.uri)

        response = toResponse(iq, u'result')
        query = response.addElement((NS_DISCO_INFO, u'query'))

        element = query.addElement(u"identity")
        element[u'category'] = u'conference' # required
        element[u'type'] = u'text' # required
        element[u"name"] = u'Romeo and Juliet, Act II, Scene II' # optional

        element = query.addElement("feature")
        element[u'var'] = u'http://jabber.org/protocol/disco#info' # required

        element = query.addElement(u"feature")
        element[u'var'] = u'http://jabber.org/protocol/muc'

        d.callback(response)
        return d


    def test_requestInfoFrom(self):
        """
        A disco info request can be sent with an explicit sender address.
        """
        d = self.protocol.requestInfo(JID(u'example.org'),
                                      sender=JID(u'test.example.org'))

        iq = self.stub.output[-1]
        self.assertEqual(u'test.example.org', iq.getAttribute(u'from'))

        response = toResponse(iq, u'result')
        response.addElement((NS_DISCO_INFO, u'query'))

        d.callback(response)
        return d



class DiscoHandlerTest(unittest.TestCase, TestableRequestHandlerMixin):
    """
    Tests for L{disco.DiscoHandler}.
    """

    def setUp(self):
        self.service = disco.DiscoHandler()


    def test_connectionInitializedObserveInfo(self):
        """
        An observer for Disco Info requests is setup on stream initialization.
        """
        xml = """<iq from='test@example.com' to='example.com'
                     type='get'>
                   <query xmlns='%s'/>
                 </iq>""" % NS_DISCO_INFO

        def handleRequest(iq):
            called.append(iq)

        called = []
        self.service.xmlstream = utility.EventDispatcher()
        self.service.handleRequest = handleRequest
        self.service.connectionInitialized()
        self.service.xmlstream.dispatch(parseXml(xml))
        self.assertEqual(1, len(called))


    def test_connectionInitializedObserveItems(self):
        """
        An observer for Disco Items requests is setup on stream initialization.
        """
        xml = """<iq from='test@example.com' to='example.com'
                     type='get'>
                   <query xmlns='%s'/>
                 </iq>""" % NS_DISCO_ITEMS

        def handleRequest(iq):
            called.append(iq)

        called = []
        self.service.xmlstream = utility.EventDispatcher()
        self.service.handleRequest = handleRequest
        self.service.connectionInitialized()
        self.service.xmlstream.dispatch(parseXml(xml))
        self.assertEqual(1, len(called))


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


    def test_onDiscoInfoWithNoFromAttribute(self):
        """
        Disco info request without a from attribute has requestor None.
        """
        xml = """<iq to='example.com'
                     type='get'>
                   <query xmlns='%s'/>
                 </iq>""" % NS_DISCO_INFO

        def info(requestor, target, nodeIdentifier):
            self.assertEqual(None, requestor)

            return defer.succeed([
                disco.DiscoIdentity('dummy', 'generic', 'Generic Dummy Entity'),
                disco.DiscoFeature('jabber:iq:version')
            ])

        self.service.info = info
        d = self.handleRequest(xml)
        return d


    def test_onDiscoInfoWithNoToAttribute(self):
        """
        Disco info request without a to attribute has target None.
        """
        xml = """<iq from='test@example.com'
                     type='get'>
                   <query xmlns='%s'/>
                 </iq>""" % NS_DISCO_INFO

        def info(requestor, target, nodeIdentifier):
            self.assertEqual(JID('test@example.com'), requestor)

            return defer.succeed([
                disco.DiscoIdentity('dummy', 'generic', 'Generic Dummy Entity'),
                disco.DiscoFeature('jabber:iq:version')
            ])

        self.service.info = info
        d = self.handleRequest(xml)
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


    def test_onDiscoInfoWithNodeNoResults(self):
        """
        An info request for a node with no results returns items-not-found.
        """
        xml = """<iq from='test@example.com' to='example.com'
                     type='get'>
                   <query xmlns='%s' node='test'/>
                 </iq>""" % NS_DISCO_INFO

        def cb(exc):
            self.assertEquals('item-not-found', exc.condition)

        def info(requestor, target, nodeIdentifier):
            self.assertEqual('test', nodeIdentifier)

            return defer.succeed([])

        self.service.info = info
        d = self.handleRequest(xml)
        self.assertFailure(d, StanzaError)
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


    def test_infoNotDeferred(self):
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
                    return discoItems
                else:
                    return []

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


    def test_itemsNotDeferred(self):
        """
        C{info} should also collect results not returned via a deferred.
        """
        discoItems = [disco.DiscoItem(JID('example.com'), 'test', 'Test node')]

        class DiscoResponder(XMPPHandler):
            implements(disco.IDisco)

            def getDiscoItems(self, requestor, target, nodeIdentifier):
                if not nodeIdentifier:
                    return discoItems
                else:
                    return []

        def cb(result):
            self.assertEquals(discoItems, result)

        self.service.parent = [self.service, DiscoResponder()]
        d = self.service.items(JID('test@example.com'), JID('example.com'), '')
        d.addCallback(cb)
        return d
