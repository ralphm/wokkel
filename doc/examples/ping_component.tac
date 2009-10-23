"""
An XMPP Ping server as an external server-side component.

This ping server assumes the domain C{'ping'}.
"""

from twisted.application import service
from wokkel import component
from wokkel.ping import PingHandler

# Configuration parameters

EXT_HOST = 'localhost'
EXT_PORT = 5347
SECRET = 'secret'
DOMAIN = 'ping'
LOG_TRAFFIC = True


# Set up the Twisted application

application = service.Application("Ping Component")

router = component.Router()
pingComponent = component.Component(EXT_HOST, EXT_PORT, DOMAIN, SECRET)
pingComponent.logTraffic = LOG_TRAFFIC
pingComponent.setServiceParent(application)

pingHandler = PingHandler()
pingHandler.setHandlerParent(pingComponent)
