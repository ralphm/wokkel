# Copyright (c) 2003-2007 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.disco}.
"""

from twisted.internet import defer
from twisted.trial import unittest
from twisted.words.xish.xmlstream import XmlStreamFactory
from zope.interface import implements

from wokkel.subprotocols import XMPPHandler, StreamManager

from wokkel import disco

NS_DISCO_INFO = 'http://jabber.org/protocol/disco#info'
NS_DISCO_ITEMS = 'http://jabber.org/protocol/disco#items'

class DiscoResponder(XMPPHandler):
    implements(disco.IDisco)

    def getDiscoInfo(self, requestor, target, nodeIdentifier):
        if nodeIdentifier is None:
            return defer.succeed([
                disco.DiscoIdentity('dummy', 'generic', 'Generic Dummy Entity'),
                disco.DiscoFeature('jabber:iq:version')
            ])
        else:
            return defer.succeed([])

class DiscoHandlerTest(unittest.TestCase):
    def test_DiscoInfo(self):
        factory = XmlStreamFactory()
        sm = StreamManager(factory)
        disco.DiscoHandler().setHandlerParent(sm)
        DiscoResponder().setHandlerParent(sm)
        xs = factory.buildProtocol(None)
        output = []
        xs.send = output.append
        xs.connectionMade()
        xs.dispatch(xs, "//event/stream/authd")
        xs.dataReceived("<stream>")
        xs.dataReceived("""<iq from='test@example.com' to='example.com'
                               type='get'>
                             <query xmlns='%s'/>
                           </iq>""" % NS_DISCO_INFO)
        reply = output[0]
        self.assertEqual(NS_DISCO_INFO, reply.query.uri)
        self.assertEqual(NS_DISCO_INFO, reply.query.identity.uri)
        self.assertEqual('dummy', reply.query.identity['category'])
        self.assertEqual('generic', reply.query.identity['type'])
        self.assertEqual('Generic Dummy Entity', reply.query.identity['name'])
        self.assertEqual(NS_DISCO_INFO, reply.query.feature.uri)
        self.assertEqual('jabber:iq:version', reply.query.feature['var'])

