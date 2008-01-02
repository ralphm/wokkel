# -*- test-case-name: wokkel.test.test_compat -*-
#
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.words.xish import domish

def toResponse(stanza, stanzaType=None):
    """
    Create a response stanza from another stanza.

    This takes the addressing and id attributes from a stanza to create a (new,
    empty) response stanza. The addressing attributes are swapped and the id
    copied. Optionally, the stanza type of the response can be specified.

    @param stanza: the original stanza
    @type stanza: L{domish.Element}
    @param stanzaType: optional response stanza type
    @type stanzaType: C{str}
    @return: the response stanza.
    @rtype: L{domish.Element}
    """

    toAddr = stanza.getAttribute('from')
    fromAddr = stanza.getAttribute('to')
    stanzaID = stanza.getAttribute('id')

    response = domish.Element((None, stanza.name))
    if toAddr:
        response['to'] = toAddr
    if fromAddr:
        response['from'] = fromAddr
    if stanzaID:
        response['id'] = stanzaID
    if type:
        response['type'] = stanzaType

    return response


class XmlStreamFactoryMixin(object):
    """
    XmlStream factory mixin that takes care of event handlers.

    To make sure certain event observers are set up before incoming data is
    processed, you can set up bootstrap event observers using C{addBootstrap}.

    The C{event} and C{fn} parameters correspond with the C{event} and
    C{observerfn} arguments to L{utility.EventDispatcher.addObserver}.
    """

    def __init__(self, *args, **kwargs):
        self.bootstraps = []
        self.args = args
        self.kwargs = kwargs

    def buildProtocol(self, addr):
        """
        Create an instance of XmlStream.

        The returned instance will have bootstrap event observers registered
        and will proceed to handle input on an incoming connection.
        """
        xs = self.protocol(*self.args, **self.kwargs)
        xs.factory = self
        for event, fn in self.bootstraps:
            xs.addObserver(event, fn)
        return xs

    def addBootstrap(self, event, fn):
        """
        Add a bootstrap event handler.
        """
        self.bootstraps.append((event, fn))

    def removeBootstrap(self, event, fn):
        """
        Remove a bootstrap event handler.
        """
        self.bootstraps.remove((event, fn))
