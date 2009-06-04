# -*- test-case-name: wokkel.test.test_generic -*-
#
# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
Generic XMPP protocol helpers.
"""

from zope.interface import implements

from twisted.internet import defer, protocol
from twisted.words.protocols.jabber import error, jid, xmlstream
from twisted.words.protocols.jabber.xmlstream import toResponse
from twisted.words.xish import domish, utility

try:
    from twisted.words.xish.xmlstream import BootstrapMixin
except ImportError:
    from wokkel.compat import BootstrapMixin

from wokkel import disco
from wokkel.iwokkel import IDisco
from wokkel.subprotocols import XMPPHandler

IQ_GET = '/iq[@type="get"]'
IQ_SET = '/iq[@type="set"]'

NS_VERSION = 'jabber:iq:version'
VERSION = IQ_GET + '/query[@xmlns="' + NS_VERSION + '"]'

def parseXml(string):
    """
    Parse serialized XML into a DOM structure.

    @param string: The serialized XML to be parsed, UTF-8 encoded.
    @type string: C{str}.
    @return: The DOM structure, or C{None} on empty or incomplete input.
    @rtype: L{domish.Element}
    """
    roots = []
    results = []
    elementStream = domish.elementStream()
    elementStream.DocumentStartEvent = roots.append
    elementStream.ElementEvent = lambda elem: roots[0].addChild(elem)
    elementStream.DocumentEndEvent = lambda: results.append(roots[0])
    elementStream.parse(string)
    return results and results[0] or None



def stripNamespace(rootElement):
    namespace = rootElement.uri

    def strip(element):
        if element.uri == namespace:
            element.uri = None
            if element.defaultUri == namespace:
                element.defaultUri = None
            for child in element.elements():
                strip(child)

    if namespace is not None:
        strip(rootElement)

    return rootElement



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



class XmlPipe(object):
    """
    XML stream pipe.

    Connects two objects that communicate stanzas through an XML stream like
    interface. Each of the ends of the pipe (sink and source) can be used to
    send XML stanzas to the other side, or add observers to process XML stanzas
    that were sent from the other side.

    XML pipes are usually used in place of regular XML streams that are
    transported over TCP. This is the reason for the use of the names source
    and sink for both ends of the pipe. The source side corresponds with the
    entity that initiated the TCP connection, whereas the sink corresponds with
    the entity that accepts that connection. In this object, though, the source
    and sink are treated equally.

    Unlike Jabber
    L{XmlStream<twisted.words.protocols.jabber.xmlstream.XmlStream>}s, the sink
    and source objects are assumed to represent an eternal connected and
    initialized XML stream. As such, events corresponding to connection,
    disconnection, initialization and stream errors are not dispatched or
    processed.

    @ivar source: Source XML stream.
    @ivar sink: Sink XML stream.
    """

    def __init__(self):
        self.source = utility.EventDispatcher()
        self.sink = utility.EventDispatcher()
        self.source.send = lambda obj: self.sink.dispatch(obj)
        self.sink.send = lambda obj: self.source.dispatch(obj)



class Stanza(object):
    """
    Abstract representation of a stanza.

    @ivar sender: The sending entity.
    @type sender: L{jid.JID}
    @ivar recipient: The receiving entity.
    @type recipient: L{jid.JID}
    """

    sender = None
    recipient = None
    stanzaType = None

    @classmethod
    def fromElement(Class, element):
        stanza = Class()
        stanza.parseElement(element)
        return stanza


    def parseElement(self, element):
        self.sender = jid.internJID(element['from'])
        if element.hasAttribute('from'):
            self.sender = jid.internJID(element['from'])
        if element.hasAttribute('to'):
            self.recipient = jid.internJID(element['to'])
        self.stanzaType = element.getAttribute('type')


class DeferredXmlStreamFactory(BootstrapMixin, protocol.ClientFactory):
    protocol = xmlstream.XmlStream

    def __init__(self, authenticator):
        BootstrapMixin.__init__(self)

        self.authenticator = authenticator

        deferred = defer.Deferred()
        self.deferred = deferred
        self.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self.deferred.callback)
        self.addBootstrap(xmlstream.INIT_FAILED_EVENT, deferred.errback)


    def buildProtocol(self, addr):
        """
        Create an instance of XmlStream.

        A new authenticator instance will be created and passed to the new
        XmlStream. Registered bootstrap event observers are installed as well.
        """
        xs = self.protocol(self.authenticator)
        xs.factory = self
        self.installBootstraps(xs)
        return xs


    def clientConnectionFailed(self, connector, reason):
        self.deferred.errback(reason)
