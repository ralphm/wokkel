"""
A generic XMPP router.

This router accepts external server-side component connections on port 5347,
but only on 127.0.0.1.
"""

from twisted.application import service, strports
from wokkel import component

application = service.Application("XMPP router")

router = component.Router()

componentServerFactory = component.XMPPComponentServerFactory(router)
componentServerFactory.logTraffic = True
componentServer = strports.service('tcp:5347:interface=127.0.0.1',
                                   componentServerFactory)
componentServer.setServiceParent(application)
