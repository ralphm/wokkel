# -*- test-case-name: wokkel.test.test_shim -*-
#
# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
XMPP Stanza Headers and Internet Metadata.

This protocol is specified in
U{XEP-0131<http://xmpp.org/extensions/xep-0131.html>}.
"""

from twisted.words.xish import domish

NS_SHIM = "http://jabber.org/protocol/shim"

class Headers(domish.Element):
    def __init__(self, headers):
        domish.Element.__init__(self, (NS_SHIM, 'headers'))
        for name, value in headers:
            self.addElement('header', content=value)['name'] = name

def extractHeaders(stanza):
    """
    Extract SHIM headers from stanza.

    @param stanza: The stanza to extract headers from.
    @type stanza: L{Element<twisted.words.xish.domish.Element>}
    @return: Headers as a mapping from header name to a list of values.
    @rtype: C{dict}
    """
    headers = {}

    for element in domish.generateElementsQNamed(stanza.children,
                                                 'headers', NS_SHIM):
        for header in domish.generateElementsQNamed(element.children,
                                                    'header', NS_SHIM):
            headers.setdefault(header['name'], []).append(unicode(header))

    return headers
