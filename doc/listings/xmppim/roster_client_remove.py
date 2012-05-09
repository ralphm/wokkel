import sys
from twisted.internet import reactor
from twisted.words.protocols.jabber.jid import JID
from wokkel.client import XMPPClient
from wokkel.xmppim import RosterClientProtocol

USER_JID, PASSWORD, CONTACT_JID = sys.argv[1:4]
client = XMPPClient(JID(USER_JID), PASSWORD)
roster = RosterClientProtocol()
roster.setHandlerParent(client)

d = roster.removeItem(JID(CONTACT_JID))
d.addBoth(lambda _: reactor.stop())

client.startService()
reactor.run()
