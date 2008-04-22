# -*- test-case-name: wokkel.test.test_generic -*-
#
# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
Generic XMPP protocol helpers.
"""

from zope.interface import implements

from twisted.internet import defer
from twisted.words.protocols.jabber import error
from twisted.words.protocols.jabber.xmlstream import toResponse

from wokkel import disco
from wokkel.iwokkel import IDisco
from wokkel.subprotocols import XMPPHandler

IQ_GET = '/iq[@type="get"]'
IQ_SET = '/iq[@type="set"]'

NS_VERSION = 'jabber:iq:version'
VERSION = IQ_GET + '/query[@xmlns="' + NS_VERSION + '"]'

class FallbackHandler(XMPPHandler):
    """
    XMPP subprotocol handler that catches unhandled iq requests.

    Unhandled iq requests are replied to with a service-unavailable stanza
    error.
    """

    def connectionInitialized(self):
        self.xmlstream.addObserver(IQ_SET, self.iqFallback, -1)
        self.xmlstream.addObserver(IQ_GET, self.iqFallback, -1)

    def iqFallback(self, iq):
        if iq.handled == True:
            return

        reply = error.StanzaError('service-unavailable')
        self.xmlstream.send(reply.toResponse(iq))



class VersionHandler(XMPPHandler):
    """
    XMPP subprotocol handler for XMPP Software Version.

    This protocol is described in
    U{XEP-0092<http://www.xmpp.org/extensions/xep-0092.html>}.
    """

    implements(IDisco)

    def __init__(self, name, version):
        self.name = name
        self.version = version

    def connectionInitialized(self):
        self.xmlstream.addObserver(VERSION, self.onVersion)

    def onVersion(self, iq):
        response = toResponse(iq, "result")

        query = response.addElement((NS_VERSION, "query"))
        name = query.addElement("name", content=self.name)
        version = query.addElement("version", content=self.version)
        self.send(response)

        iq.handled = True

    def getDiscoInfo(self, requestor, target, node):
        info = set()

        if not node:
            info.add(disco.DiscoFeature(NS_VERSION))

        return defer.succeed(info)

    def getDiscoItems(self, requestor, target, node):
        return defer.succeed([])
