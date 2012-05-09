"""
A basic XMPP client sending presence.
"""

from twisted.application import service
from twisted.words.protocols.jabber.jid import JID

from wokkel import client, xmppim

jid = JID("user@example.org")
password = 'secret'

application = service.Application('XMPP client')
xmppClient = client.XMPPClient(jid, password)
xmppClient.logTraffic = True
xmppClient.setServiceParent(application)

presence = xmppim.PresenceProtocol()
presence.setHandlerParent(xmppClient)
presence.available()
