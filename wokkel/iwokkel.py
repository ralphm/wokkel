# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
Wokkel interfaces.
"""

from zope.interface import Attribute, Interface

class IXMPPHandler(Interface):
    """
    Interface for XMPP protocol handlers.

    Objects that provide this interface can be added to a stream manager to
    handle of (part of) an XMPP extension protocol.
    """

    parent = Attribute("""XML stream manager for this handler""")
    xmlstream = Attribute("""The managed XML stream""")

    def setHandlerParent(parent):
        """
        Set the parent of the handler.

        @type parent: L{IXMPPHandlerCollection}
        """


    def disownHandlerParent(parent):
        """
        Remove the parent of the handler.

        @type parent: L{IXMPPHandlerCollection}
        """


    def makeConnection(xs):
        """
        A connection over the underlying transport of the XML stream has been
        established.

        At this point, no traffic has been exchanged over the XML stream
        given in C{xs}.

        This should setup L{xmlstream} and call L{connectionMade}.

        @type xs: L{XmlStream<twisted.words.protocols.jabber.XmlStream>}
        """


    def connectionMade():
        """
        Called after a connection has been established.

        This method can be used to change properties of the XML Stream, its
        authenticator or the stream manager prior to stream initialization
        (including authentication).
        """


    def connectionInitialized():
        """
        The XML stream has been initialized.

        At this point, authentication was successful, and XML stanzas can be
        exchanged over the XML stream L{xmlstream}. This method can be
        used to setup observers for incoming stanzas.
        """


    def connectionLost(reason):
        """
        The XML stream has been closed.

        Subsequent use of L{parent.send} will result in data being queued
        until a new connection has been established.

        @type reason: L{twisted.python.failure.Failure}
        """



class IXMPPHandlerCollection(Interface):
    """
    Collection of handlers.

    Contain several handlers and manage their connection.
    """

    def __iter__():
        """
        Get an iterator over all child handlers.
        """


    def addHandler(handler):
        """
        Add a child handler.

        @type handler: L{IXMPPHandler}
        """


    def removeHandler(handler):
        """
        Remove a child handler.

        @type handler: L{IXMPPHandler}
        """



class IDisco(Interface):
    """
    Interface for XMPP service discovery.
    """

    def getDiscoInfo(requestor, target, nodeIdentifier=''):
        """
        Get identity and features from this entity, node.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param target: The target entity to which the request is made.
        @type target: L{jid.JID}
        @param nodeIdentifier: The optional identifier of the node at this
                               entity to retrieve the identify and features of.
                               The default is C{''}, meaning the root node.
        @type nodeIdentifier: C{unicode}
        """

    def getDiscoItems(requestor, target, nodeIdentifier=''):
        """
        Get contained items for this entity, node.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param target: The target entity to which the request is made.
        @type target: L{jid.JID}
        @param nodeIdentifier: The optional identifier of the node at this
                               entity to retrieve the identify and features of.
                               The default is C{''}, meaning the root node.
        @type nodeIdentifier: C{unicode}
        """


class IPubSubClient(Interface):

    def itemsReceived(event):
        """
        Called when an items notification has been received for a node.

        An item can be an element named C{item} or C{retract}. Respectively,
        they signal an item being published or retracted, optionally
        accompanied with an item identifier in the C{id} attribute.

        @param event: The items event.
        @type event: L{ItemsEvent<wokkel.pubsub.ItemsEvent>}
        """


    def deleteReceived(event):
        """
        Called when a deletion notification has been received for a node.

        @param event: The items event.
        @type event: L{ItemsEvent<wokkel.pubsub.DeleteEvent>}
        """


    def purgeReceived(event):
        """
        Called when a purge notification has been received for a node.

        Upon receiving this notification all items associated should be
        considered retracted.

        @param event: The items event.
        @type event: L{ItemsEvent<wokkel.pubsub.PurgeEvent>}
        """

    def createNode(service, nodeIdentifier=None):
        """
        Create a new publish subscribe node.

        @param service: The publish-subscribe service entity.
        @type service: L{jid.JID}
        @param nodeIdentifier: Optional suggestion for the new node's
                               identifier. If omitted, the creation of an
                               instant node will be attempted.
        @type nodeIdentifier: L{unicode}
        @return: a deferred that fires with the identifier of the newly created
                 node. Note that this can differ from the suggested identifier
                 if the publish subscribe service chooses to modify or ignore
                 the suggested identifier.
        @rtype: L{defer.Deferred}
        """

    def deleteNode(service, nodeIdentifier):
        """
        Delete a node.

        @param service: The publish-subscribe service entity.
        @type service: L{jid.JID}
        @param nodeIdentifier: Identifier of the node to be deleted.
        @type nodeIdentifier: L{unicode}
        @rtype: L{defer.Deferred}
        """

    def subscribe(service, nodeIdentifier, subscriber):
        """
        Subscribe to a node with a given JID.

        @param service: The publish-subscribe service entity.
        @type service: L{jid.JID}
        @param nodeIdentifier: Identifier of the node to subscribe to.
        @type nodeIdentifier: L{unicode}
        @param subscriber: JID to subscribe to the node.
        @type subscriber: L{jid.JID}
        @rtype: L{defer.Deferred}
        """

    def unsubscribe(service, nodeIdentifier, subscriber):
        """
        Unsubscribe from a node with a given JID.

        @param service: The publish-subscribe service entity.
        @type service: L{jid.JID}
        @param nodeIdentifier: Identifier of the node to unsubscribe from.
        @type nodeIdentifier: L{unicode}
        @param subscriber: JID to unsubscribe from the node.
        @type subscriber: L{jid.JID}
        @rtype: L{defer.Deferred}
        """

    def publish(service, nodeIdentifier, items=[]):
        """
        Publish to a node.

        Node that the C{items} parameter is optional, because so-called
        transient, notification-only nodes do not use items and publish
        actions only signify a change in some resource.

        @param service: The publish-subscribe service entity.
        @type service: L{jid.JID}
        @param nodeIdentifier: Identifier of the node to publish to.
        @type nodeIdentifier: L{unicode}
        @param items: List of item elements.
        @type items: L{list} of L{Item}
        @rtype: L{defer.Deferred}
        """


class IPubSubService(Interface):
    """
    Interface for an XMPP Publish Subscribe Service.

    All methods that are called as the result of an XMPP request are to
    return a deferred that fires when the requested action has been performed.
    Alternatively, exceptions maybe raised directly or by calling C{errback}
    on the returned deferred.
    """

    def notifyPublish(service, nodeIdentifier, notifications):
        """
        Send out notifications for a publish event.

        @param service: The entity the notifications will originate from.
        @type service: L{jid.JID}
        @param nodeIdentifier: The identifier of the node that was published
                               to.
        @type nodeIdentifier: C{unicode}
        @param notifications: The notifications as tuples of subscriber, the
                              list of subscriptions and the list of items to be
                              notified.
        @type notifications: C{list} of (L{jid.JID}, C{list} of
                             L{Subscription<wokkel.pubsub.Subscription>},
                             C{list} of L{domish.Element})
        """

    def notifyDelete(service, nodeIdentifier, subscribers,
                     redirectURI=None):
        """
        Send out node deletion notifications.

        @param service: The entity the notifications will originate from.
        @type service: L{jid.JID}
        @param nodeIdentifier: The identifier of the node that was deleted.
        @type nodeIdentifier: C{unicode}
        @param subscribers: The subscribers for which a notification should
                            be sent out.
        @type subscribers: C{list} of L{jid.JID}
        @param redirectURI: Optional XMPP URI of another node that subscribers
                            are redirected to.
        @type redirectURI: C{str}
        """

    def publish(requestor, service, nodeIdentifier, items):
        """
        Called when a publish request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @param nodeIdentifier: The identifier of the node to publish to.
        @type nodeIdentifier: C{unicode}
        @param items: The items to be published as L{domish} elements.
        @type items: C{list} of C{domish.Element}
        @return: deferred that fires on success.
        @rtype: L{defer.Deferred}
        """

    def subscribe(requestor, service, nodeIdentifier, subscriber):
        """
        Called when a subscribe request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @param nodeIdentifier: The identifier of the node to subscribe to.
        @type nodeIdentifier: C{unicode}
        @param subscriber: The entity to be subscribed.
        @type subscriber: L{jid.JID}
        @return: A deferred that fires with a
                 L{Subscription<wokkel.pubsub.Subscription>}.
        @rtype: L{defer.Deferred}
        """

    def unsubscribe(requestor, service, nodeIdentifier, subscriber):
        """
        Called when a subscribe request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @param nodeIdentifier: The identifier of the node to unsubscribe from.
        @type nodeIdentifier: C{unicode}
        @param subscriber: The entity to be unsubscribed.
        @type subscriber: L{jid.JID}
        @return: A deferred that fires with C{None} when unsubscription has
                 succeeded.
        @rtype: L{defer.Deferred}
        """

    def subscriptions(requestor, service):
        """
        Called when a subscriptions retrieval request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @return: A deferred that fires with a C{list} of subscriptions as
                 L{Subscription<wokkel.pubsub.Subscription>}.
        @rtype: L{defer.Deferred}
        """

    def affiliations(requestor, service):
        """
        Called when a affiliations retrieval request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @return: A deferred that fires with a C{list} of affiliations as
                 C{tuple}s of (node identifier as C{unicode}, affiliation state
                 as C{str}). The affiliation can be C{'owner'}, C{'publisher'},
                 or C{'outcast'}.
        @rtype: L{defer.Deferred}
        """

    def create(requestor, service, nodeIdentifier):
        """
        Called when a node creation request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @param nodeIdentifier: The suggestion for the identifier of the node to
                               be created. If the request did not include a
                               suggestion for the node identifier, the value
                               is C{None}.
        @type nodeIdentifier: C{unicode} or C{NoneType}
        @return: A deferred that fires with a C{unicode} that represents
                 the identifier of the new node.
        @rtype: L{defer.Deferred}
        """

    def getConfigurationOptions():
        """
        Retrieve all known node configuration options.

        The returned dictionary holds the possible node configuration options
        by option name. The value of each entry represents the specifics for
        that option in a dictionary:

         - C{'type'} (C{str}): The option's type (see
           L{Field<wokkel.data_form.Field>}'s doc string for possible values).
         - C{'label'} (C{unicode}): A human readable label for this option.
         - C{'options'} (C{dict}): Optional list of possible values for this
           option.

        Example::

            {
            "pubsub#persist_items":
                {"type": "boolean",
                 "label": "Persist items to storage"},
            "pubsub#deliver_payloads":
                {"type": "boolean",
                 "label": "Deliver payloads with event notifications"},
            "pubsub#send_last_published_item":
                {"type": "list-single",
                 "label": "When to send the last published item",
                 "options": {
                     "never": "Never",
                     "on_sub": "When a new subscription is processed"}
                }
            }

        @rtype: C{dict}.
        """

    def getDefaultConfiguration(requestor, service, nodeType):
        """
        Called when a default node configuration request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @param nodeType: The type of node for which the configuration is
                         retrieved, C{'leaf'} or C{'collection'}.
        @type nodeType: C{str}
        @return: A deferred that fires with a C{dict} representing the default
                 node configuration. Keys are C{str}s that represent the
                 field name. Values can be of types C{unicode}, C{int} or
                 C{bool}.
        @rtype: L{defer.Deferred}
        """

    def getConfiguration(requestor, service, nodeIdentifier):
        """
        Called when a node configuration retrieval request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @param nodeIdentifier: The identifier of the node to retrieve the
                               configuration from.
        @type nodeIdentifier: C{unicode}
        @return: A deferred that fires with a C{dict} representing the node
                 configuration. Keys are C{str}s that represent the field name.
                 Values can be of types C{unicode}, C{int} or C{bool}.
        @rtype: L{defer.Deferred}
        """

    def setConfiguration(requestor, service, nodeIdentifier, options):
        """
        Called when a node configuration change request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @param nodeIdentifier: The identifier of the node to change the
                               configuration of.
        @type nodeIdentifier: C{unicode}
        @return: A deferred that fires with C{None} when the node's
                 configuration has been changed.
        @rtype: L{defer.Deferred}
        """

    def items(requestor, service, nodeIdentifier, maxItems, itemIdentifiers):
        """
        Called when a items retrieval request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @param nodeIdentifier: The identifier of the node to retrieve items
                               from.
        @type nodeIdentifier: C{unicode}
        """

    def retract(requestor, service, nodeIdentifier, itemIdentifiers):
        """
        Called when a item retraction request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @param nodeIdentifier: The identifier of the node to retract items
                               from.
        @type nodeIdentifier: C{unicode}
        """

    def purge(requestor, service, nodeIdentifier):
        """
        Called when a node purge request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @param nodeIdentifier: The identifier of the node to be purged.
        @type nodeIdentifier: C{unicode}
        """

    def delete(requestor, service, nodeIdentifier):
        """
        Called when a node deletion request has been received.

        @param requestor: The entity the request originated from.
        @type requestor: L{jid.JID}
        @param service: The entity the request was addressed to.
        @type service: L{jid.JID}
        @param nodeIdentifier: The identifier of the node to be delete.
        @type nodeIdentifier: C{unicode}
        """
