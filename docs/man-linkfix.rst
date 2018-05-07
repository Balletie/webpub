.. click:: webpub.cli:linkfix_cmd
   :prog: webpub-linkfix

Examples
--------

A typical run might look as follows::

  webpub-linkfix -u /www -f /www

This interactively fixes any relative links in all HTML and CSS
files. Anytime a broken link is found, the program asks for an action
on what to do with the link.

The program can also be run non-interactively, by specifying an action
beforehand::

  webpub-linkfix -u /www --action rm -f /www

The above example deletes all broken links that are found, replacing
it with the contents of the node (if any).

See also
--------

:manpage:`webpub(1)`, :manpage:`webpub-suttaref(1)`
