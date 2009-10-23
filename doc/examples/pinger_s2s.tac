"""
An XMPP Ping client as a standalone server via s2s.

This ping client accepts and initiates server-to-server connections using
dialback and listens on C{127.0.1.1} with the domain set to the default
hostname of this machine.
"""

import socket

from twisted.application import service, strports
from twisted.words.protocols.jabber.jid import JID
from wokkel import component, server
from pinger import Pinger

# Configuration parameters

S2S_PORT = 'tcp:5269:interface=127.0.1.1'
SECRET = 'secret'
DOMAIN = socket.gethostname()
OTHER_DOMAIN = 'localhost'
LOG_TRAFFIC = True


# Set up the Twisted application

application = service.Application("Pinger Server")

router = component.Router()

serverService = server.ServerService(router, domain=DOMAIN, secret=SECRET)
serverService.logTraffic = LOG_TRAFFIC

s2sFactory = server.XMPPS2SServerFactory(serverService)
s2sFactory.logTraffic = LOG_TRAFFIC
s2sService = strports.service(S2S_PORT, s2sFactory)
s2sService.setServiceParent(application)

pingerComponent = component.InternalComponent(router, DOMAIN)
pingerComponent.logTraffic = LOG_TRAFFIC
pingerComponent.setServiceParent(application)

pingerHandler = Pinger(JID(OTHER_DOMAIN), JID(DOMAIN))
pingerHandler.setHandlerParent(pingerComponent)
