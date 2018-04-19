import requests
import html5lib as html5
from inxs import Rule, Transformation

from webpub.css import replace_urls
from webpub.handlers import handle_routes, ConstDestMimetypeRoute
from webpub.util import (
    tostring, write_out, guard_dry_run, guard_overwrite, has_link
)
from webpub.route import (
    route_url, check_and_fix_absolute, has_relative_url, has_absolute_url
)


def linkfix_document(routes, filepath, currentpath, fallback_url):
    context = locals().copy()

    transformation = Transformation(
        Rule([has_link, has_relative_url], route_url),
        Rule([has_link, has_absolute_url], check_and_fix_absolute),
        context=context,
    )

    with open(currentpath) as doc:
        doc_tree = html5.parse(
            doc, treebuilder='lxml',
            namespaceHTMLElements=False
        )

    root = doc_tree.getroot()
    with requests.Session() as s:
        return transformation(root, session=s)


linkfix_document.verbose_name = "Fix links"


linkfix_mime_handlers = {
    'text/html': (linkfix_document, guard_dry_run, guard_overwrite,
                  tostring, write_out),
    'text/css': (replace_urls, guard_dry_run, guard_overwrite, write_out),
    'application/xhtml+xml': 'text/html',
    '*/*': (),
}


class LinkFixRoute(ConstDestMimetypeRoute):
    def get_mime_to_handlers(self):
        return linkfix_mime_handlers


def linkfix_routes(filenames, output_dir):
    for root_dir, fname in filenames:
        yield LinkFixRoute(fname, root_dir, output_dir)


def fixlinks(filenames, fallback_url, dry_run, output_dir, overwrite):
    if dry_run:
        print("Dry run; no files will be written")
    context = {
        'dry_run': dry_run,
        'overwrite': overwrite,
        'output_dir': output_dir or '.',
        'fallback_url': fallback_url,
    }
    routes = linkfix_routes(filenames, output_dir)
    handle_routes(routes, context)
