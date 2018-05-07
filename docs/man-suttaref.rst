.. click:: webpub.cli:sutta_cross_ref_cmd
   :prog: webpub-suttaref

Examples
--------

A typical run might look as follows::

  webpub-suttaref -u /www -f /www

This searches for any sutta references in the text contents of all
HTML files. Existing references are ignored. When a sutta reference
doesn't have a working link, an interactive prompt asks for the action
to take. For references to Pātimokkha rules and to rules from the
Cullavagga, an interactive prompt is always presented since those
can't be determined automatically.

One may also specify an action to take on references that aren't found
beforehand::

  webpub-suttaref -u /www --action cont -f /www

In the above example, unfound references are left as-is.

See also
--------

To fix existing broken sutta references, use
:manpage:`webpub-linkfix(1)`.
