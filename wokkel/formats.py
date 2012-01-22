# Copyright (c) Ralph Meijer.
# See LICENSE for details.

NS_MOOD = 'http://jabber.org/protocol/mood'
NS_TUNE = 'http://jabber.org/protocol/tune'

class Mood:
    """
    User mood.

    This represents a user's mood, as defined in
    U{XEP-0107<http://xmpp.org/extensions/xep-0107.html>}.

    @ivar value: The mood value.
    @ivar text: The optional natural-language description of, or reason
                for the mood.
    """

    def __init__(self, value, text=None):
        self.value = value
        self.text = text

    def fromXml(self, element):
        """
        Get a Mood instance from an XML representation.

        This class method parses the given XML document into a L{Mood}
        instances.

        @param element: The XML mood document.
        @type element: object providing
                       L{IElement<twisted.words.xish.domish.IElement>}
        @return: A L{Mood} instance or C{None} if C{element} was not a mood
                 document or if there was no mood value element.
        """
        if element.uri != NS_MOOD or element.name != 'mood':
            return None

        value = None
        text = None

        for child in element.elements():
            if child.uri != NS_MOOD:
                continue

            if child.name == 'text':
                text = unicode(child)
            else:
                value = child.name

        if value:
            return Mood(value, text)
        else:
            return None

    fromXml = classmethod(fromXml)

class Tune:
    """
    User tune.

    This represents a user's mood, as defined in
    U{XEP-0118<http://xmpp.org/extensions/xep-0118.html>}.

    @ivar artist: The artist or performer of the song or piece.
    @type artist: C{unicode}
    @ivar length: The duration of the song or piece in seconds.
    @type length: C{int}
    @ivar source: The collection (e.g. album) or other source.
    @type source: C{unicode}
    @ivar title: The title of the song or piece
    @type title: C{unicode}
    @ivar track: A unique identifier for the tune; e.g. the track number within
                 the collection or the specific URI for the object.
    @type track: C{unicode}
    @ivar uri: A URI pointing to information about the song, collection, or
               artist.
    @type uri: C{str}

    """

    artist = None
    length = None
    source = None
    title = None
    track = None
    uri = None

    def fromXml(self, element):
        """
        Get a Tune instance from an XML representation.

        This class method parses the given XML document into a L{Tune}
        instances.

        @param element: The XML tune document.
        @type element: object providing
                       L{IElement<twisted.words.xish.domish.IElement>}
        @return: A L{Tune} instance or C{None} if C{element} was not a tune
                 document.
        """
        if element.uri != NS_TUNE or element.name != 'tune':
            return None

        tune = Tune()

        for child in element.elements():
            if child.uri != NS_TUNE:
                continue

            if child.name in ('artist', 'source', 'title', 'track', 'uri'):
                setattr(tune, child.name, unicode(child))
            elif child.name == 'length':
                try:
                    tune.length = int(unicode(child))
                except ValueError:
                    pass

        return tune

    fromXml = classmethod(fromXml)
