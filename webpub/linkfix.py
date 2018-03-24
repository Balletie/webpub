import os

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


def linkfix_routes(filenames, basedir, custom_routes, context):
    for fname in filenames:
        basename = os.path.basename(fname)
        old_path = os.path.join(
            context['root_dir'],
            os.path.join(basedir, basename)
        )

        yield LinkFixRoute(old_path, fname)

    for src, dest in custom_routes:
        yield LinkFixRoute(src, dest)


def fixlinks(filenames, fallback_url, dry_run, basedir, custom_routes,
             output_dir, overwrite):
    if dry_run:
        print("Dry run; no files will be written")
    filenames = [os.path.realpath(fname) for fname in filenames]
    root_dir = os.path.commonpath(filenames)
    context = {
        'dry_run': dry_run,
        'overwrite': overwrite,
        'root_dir': root_dir,
        'output_dir': output_dir or root_dir,
        'fallback_url': fallback_url,
    }
    routes = linkfix_routes(filenames, basedir, custom_routes,
                            context)
    handle_routes(routes, context)
