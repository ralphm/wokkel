XMPP IM protocol support
========================

Roster Management
-----------------

A roster holds a collection of contacts for a user. Typically a user has one
roster kept by the user's server, but rosters may also be kept by other
entities. Usually, a client requests a user's roster right after
authentication, and is then notified of any changes to the roster. A client may
also modify the roster, on behalf of the user, by setting or removing roster
items. 

Requesting the roster
^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: listings/xmppim/roster_client_get.py
   :language: python
   :linenos:

Receiving roster pushes
^^^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: listings/xmppim/roster_client_push.py
   :language: python
   :linenos:

Set the name of a contact
^^^^^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: listings/xmppim/roster_client_set_name.py
   :language: python
   :linenos:

Remove a contact
^^^^^^^^^^^^^^^^

.. literalinclude:: listings/xmppim/roster_client_remove.py
   :language: python
   :linenos:

Roster versioning
^^^^^^^^^^^^^^^^^

Some XMPP servers support roster versioning. A client can keep a cache of the
roster by requesting it and applying changes as roster pushes come in. Each
version of the roster is marked with a version identifier. This can be used
to request the roster upon reconnect. The server can then choose to send the
difference between the requested and current version as roster pushed,
instead of returning the complete roster.

When no roster was cached by the client, yet, a client passes the empty
string (``''``) to ``getRoster`` to bootstrap the process.

This example will force a reconnect 15 seconds after authentication.

.. literalinclude:: listings/xmppim/roster_client_versioning.py
   :language: python
   :linenos:
