"""
An XMPP Ping server as a standalone server with external component service.

This ping responder server uses the C{ping} domain, and also accepts External
Component connections on port C{5347}, but only on C{127.0.0.1}.
"""

from twisted.application import service, strports
from wokkel import component
from wokkel.ping import PingHandler

# Configuration parameters

EXT_PORT = 'tcp:5347:interface=127.0.0.1'
SECRET = 'secret'
DOMAIN = 'ping'
LOG_TRAFFIC = True


# Set up the Twisted application

application = service.Application("XMPP Ping Server")

router = component.Router()

componentServerFactory = component.XMPPComponentServerFactory(router, SECRET)
componentServerFactory.logTraffic = LOG_TRAFFIC
componentServer = strports.service(EXT_PORT, componentServerFactory)
componentServer.setServiceParent(application)

pingComponent = component.InternalComponent(router, DOMAIN)
pingComponent.logTraffic = LOG_TRAFFIC
pingComponent.setServiceParent(application)

pingHandler = PingHandler()
pingHandler.setHandlerParent(pingComponent)
