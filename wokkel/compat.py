# -*- test-case-name: wokkel.test.test_compat -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Compatibility module to provide backwards compatibility with Twisted features.
"""

from __future__ import division, absolute_import

from twisted.words.protocols.jabber import xmlstream

class IQ(xmlstream.IQ):
    def __init__(self, *args, **kwargs):
        # Make sure we have a reactor parameter
        try:
            reactor = kwargs['reactor']
        except KeyError:
            from twisted.internet import reactor
        kwargs['reactor'] = reactor

        # Check if IQ's init accepts the reactor parameter
        try:
            xmlstream.IQ.__init__(self, *args, **kwargs)
        except TypeError:
            # Guess not. Remove the reactor parameter and try again.
            del kwargs['reactor']
            xmlstream.IQ.__init__(self, *args, **kwargs)

            # Patch the XmlStream instance so that it has a _callLater
            self._xmlstream._callLater = reactor.callLater



__all__ = ['IQ']
