"""
A basic XMPP client.
"""

from twisted.application import service
from twisted.words.protocols.jabber.jid import JID

from wokkel import client

jid = JID("user@example.org")
password = 'secret'

application = service.Application('XMPP client')
xmppClient = client.XMPPClient(jid, password)
xmppClient.logTraffic = True
xmppClient.setServiceParent(application)
