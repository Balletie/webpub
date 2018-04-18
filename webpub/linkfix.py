from webpub.transform_document import linkfix_document
from webpub.css import replace_urls
from webpub.handlers import handle_routes, ConstDestMimetypeRoute
from webpub.util import tostring, write_out, guard_dry_run, guard_overwrite


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
