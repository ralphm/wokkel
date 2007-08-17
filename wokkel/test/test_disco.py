# Copyright (c) 2003-2007 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.disco}.
"""

from twisted.internet import defer
from twisted.test import proto_helpers
from twisted.trial import unittest
from twisted.words.xish.xmlstream import XmlStreamFactory
from zope.interface import implements

from wokkel.subprotocols import XMPPHandler, StreamManager

from wokkel import disco

NS_DISCO_INFO = 'http://jabber.org/protocol/disco#info'
NS_DISCO_ITEMS = 'http://jabber.org/protocol/disco#items'

class DiscoResponder(XMPPHandler):
    implements(disco.IDisco)

    def getDiscoInfo(self, nodeIdentifier):
        if nodeIdentifier is None:
            return defer.succeed([
                disco.Identity('dummy', 'generic', 'Generic Dummy Entity'),
                disco.Feature('jabber:iq:version')
            ])
        else:
            return defer.succeed([])

class DiscoHandlerTest(unittest.TestCase):
    def test_DiscoInfo(self):
        factory = XmlStreamFactory()
        sm = StreamManager(factory)
        sm.addHandler(disco.DiscoHandler())
        sm.addHandler(DiscoResponder())
        xs = factory.buildProtocol(None)
        xs.transport = proto_helpers.StringTransport()
        xs.connectionMade()
        xs.dataReceived("<stream>")
        xs.dataReceived("""<iq from='test@example.com' type='get'>
                             <query xmlns='%s'/>
                           </iq>""" % NS_DISCO_INFO)
