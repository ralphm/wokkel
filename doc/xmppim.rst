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

Remove a contact
^^^^^^^^^^^^^^^^

.. literalinclude:: listings/xmppim/roster_client_remove.py
   :language: python
   :linenos:
