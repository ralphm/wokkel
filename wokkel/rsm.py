# -*- coding: utf-8 -*-
# -*- test-case-name: wokkel.test.test_rsm -*-
#
# Copyright (c) Adrien Cossa, Jérôme Poisson
# See LICENSE for details.

"""
XMPP Result Set Management protocol.

This protocol is specified in
U{XEP-0059<http://xmpp.org/extensions/xep-0059.html>}.
"""

from twisted.words.xish import domish
from twisted.words.protocols.jabber import error

import pubsub
import copy


NS_RSM = 'http://jabber.org/protocol/rsm'


class RSMError(error.StanzaError):
    """
    RSM error.
    """
    def __init__(self, text=None):
        error.StanzaError.__init__(self, 'bad-request', text=text)


class RSMNotFoundError(Exception):
    """
    An expected RSM element has not been found.
    """


class RSMRequest(object):
    """
    A Result Set Management request.

    @ivar max_: limit on the number of retrieved items.
    @itype max_: C{int} or C{unicode}

    @ivar index: starting index of the requested page.
    @itype index: C{int} or C{unicode} or C{None}

    @ivar after: ID of the element immediately preceding the page.
    @itype after: C{unicode}

    @ivar before: ID of the element immediately following the page.
    @itype before: C{unicode}
    """

    def __init__(self, max_=10, after=None, before=None, index=None):
        self.max = int(max_)

        if index is not None:
            assert after is None and before is None
            index = int(index)
        self.index = index

        if after is not None:
            assert before is None
            assert isinstance(after, basestring)
        self.after = after

        if before is not None:
            assert isinstance(before, basestring)
        self.before = before

    def __str__(self):
        return "RSM Request: max={0.max} after={0.after} before={0.before} index={0.index}".format(self)

    @classmethod
    def fromElement(cls, element):
        """Parse the given request element.

        @param element: request containing a set element, or set element itself.
        @type element: L{domish.Element}

        @return: RSMRequest instance.
        @rtype: L{RSMRequest}
        """

        if element.name == 'set' and element.uri == NS_RSM:
            set_elt = element
        else:
            try:
                set_elt = element.elements(NS_RSM, 'set').next()
            except StopIteration:
                raise RSMNotFoundError()

        try:
            before_elt = set_elt.elements(NS_RSM, 'before').next()
        except StopIteration:
            before = None
        else:
            before = unicode(before_elt)

        try:
            after_elt = set_elt.elements(NS_RSM, 'after').next()
        except StopIteration:
            after = None
        else:
            after = unicode(after_elt)
            if not after:
                raise RSMError("<after/> element can't be empty in RSM request")

        try:
            max_elt = set_elt.elements(NS_RSM, 'max').next()
        except StopIteration:
            # FIXME: even if it doesn't make a lot of sense without it
            #        <max/> element is not mandatory in XEP-0059
            raise RSMError("RSM request is missing its 'max' element")
        else:
            try:
                max_ = int(unicode(max_elt))
            except ValueError:
                raise RSMError("bad value for 'max' element")

        try:
            index_elt = set_elt.elements(NS_RSM, 'index').next()
        except StopIteration:
            index = None
        else:
            try:
                index = int(unicode(index_elt))
            except ValueError:
                raise RSMError("bad value for 'index' element")

        return RSMRequest(max_, after, before, index)

    def toElement(self):
        """
        Return the DOM representation of this RSM request.

        @rtype: L{domish.Element}
        """
        set_elt = domish.Element((NS_RSM, 'set'))
        set_elt.addElement('max', content=unicode(self.max))

        if self.index is not None:
            set_elt.addElement('index', content=unicode(self.index))

        if self.before is not None:
            if self.before == '':  # request the last page
                set_elt.addElement('before')
            else:
                set_elt.addElement('before', content=self.before)

        if self.after is not None:
            set_elt.addElement('after', content=self.after)

        return set_elt

    def render(self, element):
        """Embed the DOM representation of this RSM request in the given element.

        @param element: Element to contain the RSM request.
        @type element: L{domish.Element}

        @return: RSM request element.
        @rtype: L{domish.Element}
        """
        set_elt = self.toElement()
        element.addChild(set_elt)

        return set_elt


class RSMResponse(object):
    """
    A Result Set Management response.

    @ivar first: ID of the first element of the returned page.
    @itype first: C{unicode}

    @ivar last: ID of the last element of the returned page.
    @itype last: C{unicode}

    @ivar index: starting index of the returned page.
    @itype index: C{int}

    @ivar count: total number of items.
    @itype count: C{int}

    """

    def __init__(self, first=None, last=None, index=None, count=None):
        if first is None:
            assert last is None and index is None
        if last is None:
            assert first is None
        self.first = first
        self.last = last
        if count is not None:
            self.count = int(count)
        else:
            self.count = None
        if index is not None:
            self.index = int(index)
        else:
            self.index = None

    def __str__(self):
        return "RSM Request: first={0.first} last={0.last} index={0.index} count={0.count}".format(self)

    @classmethod
    def fromElement(cls, element):
        """Parse the given response element.

        @param element: response element.
        @type element: L{domish.Element}

        @return: RSMResponse instance.
        @rtype: L{RSMResponse}
        """
        try:
            set_elt = element.elements(NS_RSM, 'set').next()
        except StopIteration:
            raise RSMNotFoundError()

        try:
            first_elt = set_elt.elements(NS_RSM, 'first').next()
        except StopIteration:
            first = None
            index = None
        else:
            first = unicode(first_elt)
            try:
                index = int(first_elt['index'])
            except KeyError:
                index = None
            except ValueError:
                raise RSMError("bad index in RSM response")

        try:
            last_elt = set_elt.elements(NS_RSM, 'last').next()
        except StopIteration:
            if first is not None:
                raise RSMError("RSM response is missing its 'last' element")
            else:
                last = None
        else:
            if first is None:
                raise RSMError("RSM response is missing its 'first' element")
            last = unicode(last_elt)

        try:
            count_elt = set_elt.elements(NS_RSM, 'count').next()
        except StopIteration:
            count = None
        else:
            try:
                count = int(unicode(count_elt))
            except ValueError:
                raise RSMError("invalid count in RSM response")

        return RSMResponse(first, last, index, count)

    def toElement(self):
        """
        Return the DOM representation of this RSM request.

        @rtype: L{domish.Element}
        """
        set_elt = domish.Element((NS_RSM, 'set'))
        if self.first is not None:
            first_elt = set_elt.addElement('first', content=self.first)
            if self.index is not None:
                first_elt['index'] = unicode(self.index)

            set_elt.addElement('last', content=self.last)

        if self.count is not None:
            set_elt.addElement('count', content=unicode(self.count))

        return set_elt

    def render(self, element):
        """Embed the DOM representation of this RSM response in the given element.

        @param element: Element to contain the RSM response.
        @type element:  L{domish.Element}

        @return: RSM request element.
        @rtype: L{domish.Element}
        """
        set_elt = self.toElement()
        element.addChild(set_elt)
        return set_elt

    def toDict(self):
        """Return a dict representation of the object.

        @return: a dict of strings.
        @rtype: C{dict} binding C{unicode} to C{unicode}
        """
        result = {}
        for attr in ('first', 'last', 'index', 'count'):
            value = getattr(self, attr)
            if value is not None:
                result[attr] = unicode(value)
        return result


class PubSubRequest(pubsub.PubSubRequest):
    """PubSubRequest extension to handle RSM.

    @ivar rsm: RSM request instance.
    @type rsm: L{RSMRequest}
    """

    rsm = None
    _parameters = copy.deepcopy(pubsub.PubSubRequest._parameters)
    _parameters['items'].append('rsm')

    def _parse_rsm(self, verbElement):
        try:
            self.rsm = RSMRequest.fromElement(verbElement.parent)
        except RSMNotFoundError:
            self.rsm = None

    def _render_rsm(self, verbElement):
        if self.rsm:
            self.rsm.render(verbElement.parent)


class PubSubClient(pubsub.PubSubClient):
    """PubSubClient extension to handle RSM."""

    _request_class = PubSubRequest

    def items(self, service, nodeIdentifier, maxItems=None, itemIdentifiers=None,
              subscriptionIdentifier=None, sender=None, rsm_request=None):
        """
        Retrieve previously published items from a publish subscribe node.

        @param service: The publish subscribe service that keeps the node.
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param nodeIdentifier: The identifier of the node.
        @type nodeIdentifier: C{unicode}

        @param maxItems: Optional limit on the number of retrieved items.
        @type maxItems: C{int}

        @param itemIdentifiers: Identifiers of the items to be retrieved.
        @type itemIdentifiers: C{set}

        @param subscriptionIdentifier: Optional subscription identifier. In
            case the node has been subscribed to multiple times, this narrows
            the results to the specific subscription.
        @type subscriptionIdentifier: C{unicode}

        @param ext_data: extension data.
        @type ext_data: L{dict}

        @return: a Deferred that fires a C{list} of C{tuple} of L{domish.Element}, L{RSMResponse}.
        @rtype: L{defer.Deferred}
        """
        # XXX: we have to copy initial method instead of calling it,
        #      as original cb remove all non item elements
        request = self._request_class('items')
        request.recipient = service
        request.nodeIdentifier = nodeIdentifier
        if maxItems:
            request.maxItems = str(int(maxItems))
        request.subscriptionIdentifier = subscriptionIdentifier
        request.sender = sender
        request.itemIdentifiers = itemIdentifiers
        request.rsm = rsm_request

        def cb(iq):
            items = []
            pubsub_elt = iq.pubsub
            if pubsub_elt.items:
                for element in pubsub_elt.items.elements(pubsub.NS_PUBSUB, 'item'):
                    items.append(element)

            try:
                rsm_response = RSMResponse.fromElement(pubsub_elt)
            except RSMNotFoundError:
                rsm_response = None
            return (items, rsm_response)

        d = request.send(self.xmlstream)
        d.addCallback(cb)
        return d


class PubSubService(pubsub.PubSubService):
    """PubSubService extension to handle RSM."""

    _request_class = PubSubRequest

    def _toResponse_items(self, elts, resource, request):
        # default method only manage <item/> elements
        # but we need to add RSM set element
        rsm_elt = None
        for idx, elt in enumerate(reversed(elts)):
            if elt.name == "set" and elt.uri == NS_RSM:
                rsm_elt = elts.pop(-1-idx)
                break

        response = pubsub.PubSubService._toResponse_items(self, elts,
                                                          resource, request)
        if rsm_elt is not None:
            response.addChild(rsm_elt)

        return response
