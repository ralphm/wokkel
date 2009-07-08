"""
An XMPP Ping client as an XMPP client.

This pinger client logs in as C{pinger@example.org}.
"""

from twisted.application import service
from twisted.words.protocols.jabber.jid import JID
from wokkel import client
from pinger import Pinger

# Configuration parameters

THIS_JID = JID('pinger@example.org')
OTHER_JID = JID('ping.example.com')
SECRET = 'secret'
LOG_TRAFFIC = True


# Set up the Twisted application

application = service.Application("Pinger Component")

pingerClient = client.XMPPClient(THIS_JID, SECRET)
pingerClient.logTraffic = LOG_TRAFFIC
pingerClient.setServiceParent(application)
pingerClient.send('<presence/>') # Hello, OpenFire!

pingerHandler = Pinger(OTHER_JID)
pingerHandler.setHandlerParent(pingerClient)
