import sys
from twisted.python import log
from twisted.internet import reactor
from twisted.words.protocols.jabber.jid import JID
from wokkel.client import XMPPClient
from wokkel.xmppim import RosterClientProtocol

class RosterHandler(RosterClientProtocol):
    def gotRoster(self, roster):
        print 'Got roster:'
        for entity, item in roster.iteritems():
            print '  %r (%r)' % (entity, item.name or '')

    def connectionInitialized(self):
        RosterClientProtocol.connectionInitialized(self)
        d = self.getRoster()
        d.addCallback(self.gotRoster)
        d.addErrback(log.err)

    def removeReceived(self, request):
        print 'Contact %r was removed.' % (request.item.entity,)

    def setReceived(self, request):
        print 'Contact %r (%r) was updated.' % (request.item.entity,
                                                request.item.name)

USER_JID, PASSWORD = sys.argv[1:3]
client = XMPPClient(JID(USER_JID), PASSWORD)
roster = RosterHandler()
roster.setHandlerParent(client)

client.startService()
reactor.run()
