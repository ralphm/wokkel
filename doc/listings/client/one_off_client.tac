"""
A one-off XMPP client.
"""

from twisted.application import service
from twisted.internet import reactor
from twisted.python import log
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import IQ

from wokkel import client

NS_VERSION = 'jabber:iq:version'

def getVersion(xmlstream, target):
    def cb(result):
        version = {}
        for element in result.query.elements():
            if (element.uri == NS_VERSION and
                element.name in ('name', 'version')):
                version[element.name] = unicode(element)
        return version

    iq = IQ(xmlstream, 'get')
    iq.addElement((NS_VERSION, 'query'))
    d = iq.send(target.full())
    d.addCallback(cb)
    return d

def printVersion(version):
    print "Name: %s" % version['name'].encode('utf-8')
    print "Version: %s" % version['version'].encode('utf-8')

jid = JID("user@example.org")
password = 'secret'

application = service.Application('XMPP client')

factory = client.DeferredClientFactory(jid, password)
factory.streamManager.logTraffic = True

d = client.clientCreator(factory)
d.addCallback(lambda _: getVersion(factory.streamManager.xmlstream,
                                   JID(jid.host)))
d.addCallback(printVersion)
d.addCallback(lambda _: factory.streamManager.xmlstream.sendFooter())
d.addErrback(log.err)
d.addBoth(lambda _: reactor.callLater(1, reactor.stop))
