# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
XMPP Component Service.

This provides an XMPP server that accepts External Components connections
and accepts and initiates server-to-server connections for the specified
domain(s).
"""

from twisted.application import service, strports
from twisted.python import usage
from twisted.words.protocols.jabber import component
from wokkel import server

class Options(usage.Options):

    optParameters = [
            ('component-port', None, 'tcp:5347:interface=127.0.0.1',
                'Port components connect to'),
            ('component-secret', None, 'secret',
                'Secret components use to connect'),
            ('server-port', None, 'tcp:5269',
                'Port other servers connect to'),
            ('server-secret', None, None,
                'Shared secret for dialback verification'),
    ]

    optFlags = [
            ('verbose', 'v', 'Log traffic'),
    ]

    def __init__(self):
        usage.Options.__init__(self)
        self['domains'] = set()


    def opt_domain(self, domain):
        """
        Domain to accept server connections for. Repeat for more domains.
        """
        self['domains'].add(domain)


    def postOptions(self):
        if not self['domains']:
            raise usage.UsageError('Need at least one domain')



def makeService(config):
    s = service.MultiService()

    router = component.Router()

    # Set up the XMPP server service

    serverService = server.ServerService(router, secret=config['server-secret'])
    serverService.domains = config['domains']
    serverService.logTraffic = config['verbose']

    # Hook up XMPP server-to-server service
    s2sFactory = server.XMPPS2SServerFactory(serverService)
    s2sFactory.logTraffic = config['verbose']
    s2sService = strports.service(config['server-port'], s2sFactory)
    s2sService.setServiceParent(s)

    # Hook up XMPP external server-side component service
    cFactory = component.XMPPComponentServerFactory(router,
                                                    config['component-secret'])

    cFactory.logTraffic = config['verbose']
    cServer = strports.service(config['component-port'], cFactory)
    cServer.setServiceParent(s)

    return s
