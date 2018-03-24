import os

from lxml import html

from webpub.transform_document import linkfix_document
from webpub.css import replace_urls
from webpub.handlers import handle_routes, MimetypeRoute, AbortHandling
from webpub.util import write_out


def guard_dry_run(input, dry_run):
    if dry_run:
        raise AbortHandling("Dry run, aborting.")

    return input


def guard_overwrite(input, filepath, overwrite):
    if not overwrite and os.path.exists(filepath):
        raise AbortHandling("Overwriting disabled.")

    return input


def tostring(input):
    return html.tostring(
        input,
        doctype='<!DOCTYPE html>',
        encoding='utf-8',
        pretty_print=True,
    )


# Dict from mimetype media ranges to handlers and destination directory.
linkfix_mime_handlers = {
    'text/html': (linkfix_document, guard_dry_run, tostring, write_out),
    'text/css': (replace_urls, guard_dry_run, write_out),
    'application/xhtml+xml': 'text/html',
    '*/*': (),
}


class ConstDestMimetypeRoute(MimetypeRoute):
    def __init__(self, src, dst, mimetype=None):
        super().__init__(src, mimetype)
        self._dst = dst

    def get_mime_to_handlers(self):
        return linkfix_mime_handlers

    @property
    def dst(self):
        return self._dst

    @property
    def handlers(self):
        return self.get_handlers()


def linkfix_routes(filenames, basedir, output_dir, custom_routes, context):
    for fname in filenames:
        basename = os.path.basename(fname)
        old_path = os.path.join(
            context['root_dir'],
            os.path.join(basedir, basename)
        )
        if output_dir:
            fname = os.path.join(output_dir, fname)

        yield ConstDestMimetypeRoute(old_path, fname)

    for src, dest in custom_routes:
        yield ConstDestMimetypeRoute(src, dest)


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
        'fallback_url': fallback_url,
    }
    routes = linkfix_routes(filenames, basedir, output_dir,
                            custom_routes, context)
    handle_routes(routes, context)
