"""
An XMPP Ping client as an external server-side component.

This pinger client assumes the domain C{pinger}.
"""

from twisted.application import service
from twisted.words.protocols.jabber.jid import JID
from wokkel import component
from pinger import Pinger

# Configuration parameters

EXT_HOST = 'localhost'
EXT_PORT = 5347
SECRET = 'secret'
DOMAIN = 'pinger'
OTHER_DOMAIN = 'ping'
LOG_TRAFFIC = True


# Set up the Twisted application

application = service.Application("Pinger Component")

router = component.Router()
pingerComponent = component.Component(EXT_HOST, EXT_PORT, DOMAIN, SECRET)
pingerComponent.logTraffic = LOG_TRAFFIC
pingerComponent.setServiceParent(application)

pingerHandler = Pinger(JID(OTHER_DOMAIN), JID(DOMAIN))
pingerHandler.setHandlerParent(pingerComponent)
