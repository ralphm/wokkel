import sys
from twisted.internet import reactor
from twisted.words.protocols.jabber.jid import JID
from wokkel.client import XMPPClient
from wokkel.xmppim import RosterClientProtocol, RosterItem

USER_JID, PASSWORD, CONTACT_JID, NAME = sys.argv[1:5]
client = XMPPClient(JID(USER_JID), PASSWORD)
roster = RosterClientProtocol()
roster.setHandlerParent(client)

d = roster.setItem(RosterItem(JID(CONTACT_JID), name=NAME))
d.addBoth(lambda _: reactor.stop())

client.startService()
reactor.run()
