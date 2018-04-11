webpub
======

.. click:: webpub.cli:main
   :prog: webpub

Templates
---------

A custom Jinja2 template can be passed using :option:`--template`. The
following template variables are available to use:

``head`` & ``body``
   The contents of the head and body elements of this page.
``prev_url`` & ``next_url``
   The previous and next page, if any. If there's no previous page
   (i.e. it's the first page), then this variable is empty.
``toc_url``
   The link to the table of contents page.
``src``
   The original source path of this page within the EPUB file.
``section_title``
   The title of the current section (extracted from the table of
   contents)
``meta_title``
   The title of the entire book.
``meta_author``
   The author of the book.

For more information, see the `Jinja2 documentation
<http://jinja.pocoo.org/docs/2.10/templates/>`_.

Examples
--------

Reordering
~~~~~~~~~~

To reorder the reading order such that the second page comes first,
then the table of contents, then the first page::

   webpub -o 2 -o toc -o 1 \
          -d books/example_html example.epub

(The ``\`` in the above example is a line continuation and is added
for readability purposes)

The rest of the pages are kept in the same order. Note that this also
changes the order in the Table of Contents. If that order needs to be
different from the reading order, use the :option:`-t` /
:option:`--toc-order` option::

   webpub -o 2 -o toc -o 1 \
          -t 1 -t toc -t 2 \
          -d books/example_html example.epub

Fallback URL
~~~~~~~~~~~~

The fallback URL (:option:`-u` / :option:`--fallback-url`) enables
checking internal absolute links to see if they're working. If a
broken link was found, an interactive prompt is started asking what
needs to be done. In this example, all absolute links are tested
against the root ``/www/`` directory::

   webpub -u /www -d books/example_html example.epub

See also
--------

:manpage:`webpub-linkfix(1)`, :manpage:`webpub-suttaref`
