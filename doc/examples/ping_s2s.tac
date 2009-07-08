"""
An XMPP Ping server as a standalone server via s2s.

This ping responder accepts and initiates server-to-server connections using
dialback and listens on C{127.0.0.1} with the domain C{localhost}.
"""

from twisted.application import service, strports
from wokkel import component, server
from wokkel.ping import PingHandler

# Configuration parameters

S2S_PORT = 'tcp:5269:interface=127.0.0.1'
SECRET = 'secret'
DOMAIN = 'localhost'
LOG_TRAFFIC = True


# Set up the Twisted application

application = service.Application("Ping Server")

router = component.Router()

serverService = server.ServerService(router, domain=DOMAIN, secret=SECRET)
serverService.logTraffic = LOG_TRAFFIC

s2sFactory = server.XMPPS2SServerFactory(serverService)
s2sFactory.logTraffic = LOG_TRAFFIC
s2sService = strports.service(S2S_PORT, s2sFactory)
s2sService.setServiceParent(application)

pingComponent = component.InternalComponent(router, DOMAIN)
pingComponent.logTraffic = LOG_TRAFFIC
pingComponent.setServiceParent(application)

pingHandler = PingHandler()
pingHandler.setHandlerParent(pingComponent)
