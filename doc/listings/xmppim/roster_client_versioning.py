import sys
from twisted.python import log
from twisted.internet import reactor
from twisted.words.protocols.jabber.jid import JID
from wokkel.client import XMPPClient
from wokkel.xmppim import RosterClientProtocol

class RosterHandler(RosterClientProtocol):
    roster = None

    def gotRoster(self, roster):
        if roster is None:
            print("The cached roster is up-to-date!")
            return

        print('Got roster (%r):' % (roster.version,))
        self.roster = roster
        for entity, item in roster.items():
            print('  %r (%r)' % (entity, item.name or ''))

    def connectionInitialized(self):
        RosterClientProtocol.connectionInitialized(self)
        if self.roster is not None:
            version = self.roster.version
        else:
            version = ""
        d = self.getRoster(version)
        d.addCallback(self.gotRoster)
        d.addErrback(log.err)

        reactor.callLater(15, self.xmlstream.sendFooter)

    def removeReceived(self, request):
        print('Contact %r was removed.' % (request.item.entity,))
        del self.roster[request.item.entity]
        self.roster.version = request.version

    def setReceived(self, request):
        print('Contact %r (%r) was updated.' % (request.item.entity,
                                                request.item.name))
        self.roster[request.item.entity] = request.item
        self.roster.version = request.version

USER_JID, PASSWORD = sys.argv[1:3]
client = XMPPClient(JID(USER_JID), PASSWORD)
roster = RosterHandler()
roster.setHandlerParent(client)

client.startService()
reactor.run()
