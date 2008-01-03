# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
Unit test helpers.
"""

from twisted.words.xish.utility import EventDispatcher

class XmlStreamStub(object):
    """
    Stub for testing objects that communicate through XML Streams.

    Instances of this stub hold an object in L{xmlstream} that acts like an
    L{XmlStream<twisted.words.xish.xmlstream.XmlStream} after connection stream
    initialization. Stanzas can be sent through it by calling its C{send}
    method with an object implementing
    L{IElement<twisted.words.xish.domish.IElement>} as its first argument.
    These appear in sequence in the L{output} instance variable of the stub.

    For the reverse direction, stanzas passed to L{send} of the stub, will be
    dispatched in the stubbed XmlStream as if it was received over the wire, so
    that registered observers will be called.

    Example:

        >>> stub = XmlStreamStub()
        >>> stub.xmlstream.send(domish.Element((None, 'presence')))
        >>> stub.output[-1].toXml()
        u'<presence/>'
        >>> def cb(stanza):
        ...     print "Got: %r" stanza.toXml()
        >>> stub.xmlstream.addObserver('/presence')
        >>> stub.send(domish.Element((None, 'presence')))
        Got: u'<presence/>'

    @ivar xmlstream: Stubbed XML Stream.
    @type xmlstream: L{EventDispatcher}
    @ivar output: List of stanzas sent to the XML Stream.
    @type output: L{list}
    """

    def __init__(self):
        self.output = []
        self.xmlstream = EventDispatcher()
        self.xmlstream.send = self.output.append

    def send(self, obj):
        """
        Pass an element to the XML Stream as if received.

        @param obj: Element to be dispatched to C{self.xmlstream}.
        @type obj: object implementing
                   L{IElement<twisted.words.xish.domish.IElement>}.
        """
        self.xmlstream.dispatch(obj)
