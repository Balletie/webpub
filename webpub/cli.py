#!/usr/bin/env python
import itertools as it
import os
import zipfile as zf
import mimetypes

import mimeparse
from lxml import etree, html
import click

from webpub.transform_document import transform_document, linkfix_document
from webpub.transform_toc import transform_toc
from webpub.transform import render_template
from webpub.css import replace_urls
from webpub.util import reorder, ensure, copy_out, write_out
from webpub.handlers import handle_routes


class Route(object):
    def __init__(self, src, mimetype=None):
        self.src = src
        self._mimetype = mimetype

    @property
    def dst(self):
        raise NotImplementedError()

    @property
    def handlers(self):
        raise NotImplementedError()

    @property
    def mimetype(self):
        return self._mimetype or mimetypes.guess_type(self.src)


class IdentityRoute(Route):
    def __init__(self, src, dst, mimetype=None):
        super().__init__(src, mimetype)
        self._dst = dst

    @property
    def dst(self):
        return self._dst or os.path.basename(self.src)

    def handlers(self):
        return (copy_out,)


def _ensure_html_extension(path):
    return './' + os.path.basename(os.path.splitext(path)[0] + '.html')


# Dict from mimetype media ranges to handlers and destination directory.
default_mime_to_dst_and_handlers = {
    'application/xhtml+xml': (_ensure_html_extension,
                              (transform_document, render_template,
                               write_out)),
    'application/x-dtbncx+xml': (lambda _: './Contents.html',
                                 (transform_toc, render_template,
                                  write_out)),
    'text/css': ('./css/', (replace_urls, write_out)),
    'image/*': ('./img/', (copy_out,)),
    '*/*': ('./etc/', (copy_out,))
}


class MimetypeRoute(Route):
    def get_mime_to_dst_and_handlers(self):
        return default_mime_to_dst_and_handlers

    def get_dst_and_handlers(self):
        mimetype_handlers = self.get_mime_to_dst_and_handlers()
        mime_match = mimeparse.best_match(
            mimetype_handlers.keys(), self.mimetype
        )
        return mimetype_handlers[mime_match]

    @property
    def dst(self):
        dst, _handlers = self.get_dst_and_handlers()

        if callable(dst):
            return dst(self.src)
        return os.path.join(dst, os.path.basename(self.src))

    @property
    def handlers(self):
        _dst, handlers = self.get_dst_and_handlers()
        return handlers


ocf_namespace = {
    'ocf': 'urn:oasis:names:tc:opendocument:xmlns:container',
}

opf_namespaces = {
    'opf': 'http://www.idpf.org/2007/opf',
    'dc': 'http://purl.org/dc/elements/1.1/',
}


def add_metadata(context, metadata):
    meta_title = metadata.xpath(
        './dc:title/text()',
        namespaces=opf_namespaces
    )
    meta_author = metadata.xpath(
        './dc:creator[@opf:role="aut"]/text()',
        namespaces=opf_namespaces
    )
    context.setdefault('meta_title', meta_title[0] if meta_title else '')
    context.setdefault('meta_author', meta_author[0] if meta_author else '')


def get_toc_item(spine, manifest):
    toc_ref = ensure(
        spine.xpath('./@toc', namespaces=opf_namespaces),
        "Spine section in EPUB package does not have a 'toc' attribute"
    )
    toc_item = ensure(
        manifest.xpath('./opf:item[@id=$ref]', ref=toc_ref,
                       namespaces=opf_namespaces),
        "Couldn't find item in manifest for toc reference {}"
        " in spine section.".format(toc_ref)
    )
    return toc_item


def epub_routes(manifest, spine, metadata, context):
    spine_refs = spine.xpath(
        './opf:itemref/@idref',
        namespaces=opf_namespaces
    )
    toc_item = get_toc_item(spine, manifest)
    toc_ref = toc_item.attrib['id']
    toc_src = toc_item.attrib['href']
    context.setdefault('src_to_title', {toc_src: 'Contents'})
    context.setdefault('routes', {})
    context.setdefault('spine', [])
    context.setdefault('toc_src', toc_src)

    add_metadata(context, metadata)

    for ref in [toc_ref] + spine_refs:
        manifest_item = manifest.xpath(
            './opf:item[@id=$ref]',
            ref=ref, namespaces=opf_namespaces
        )
        if not manifest_item:
            print(
                "Warning: couldn't find item in manifest"
                "for reference {} in spine section.".format(ref)
            )
            continue
        manifest_item = manifest_item[0]
        route = MimetypeRoute(
            manifest_item.attrib['href'],
            manifest_item.attrib['media-type']
        )
        yield route
        context['spine'].append(route.src)
        manifest.remove(manifest_item)

    context['spine'] = reorder(context['spine'], context['spine_order'])

    remaining_items = manifest.xpath('./opf:item', namespaces=opf_namespaces)
    for manifest_item in remaining_items:
        yield MimetypeRoute(
            manifest_item.attrib['href'],
            manifest_item.attrib['media-type']
        )


def make_webbook(cli_context, epub_zip):
    root_path = None
    with epub_zip.open('META-INF/container.xml') as container_xml:
        container_tree = etree.parse(container_xml)
        root_path = container_tree.xpath(
            '//ocf:container/ocf:rootfiles/ocf:rootfile/@full-path',
            namespaces=ocf_namespace)

    root_path = ensure(
        root_path,
        "No filepath found in 'META-INF/container.xml'"
    )
    root_dir = os.path.dirname(root_path)

    with epub_zip.open(root_path) as package_xml:
        package_tree = etree.parse(package_xml)
        metadata = package_tree.xpath(
            '/opf:package/opf:metadata',
            namespaces=opf_namespaces
        )
        manifest = package_tree.xpath(
            '/opf:package/opf:manifest',
            namespaces=opf_namespaces
        )
        spine = package_tree.xpath(
            '/opf:package/opf:spine',
            namespaces=opf_namespaces
        )

    metadata = ensure(metadata, "No metadata section found in EPUB package.")
    manifest = ensure(manifest, "No manifest section found in EPUB package.")
    spine = ensure(spine, "No spine section found in EPUB package.")

    context = {
        'root_dir': root_dir,
        'epub_zip': epub_zip,
        'spine_order': cli_context.params['spine_order'],
        'toc_order': cli_context.params['toc_order'],
        'template': cli_context.params['template'],
        'output_dir': cli_context.params['output_dir'],
    }
    routes = epub_routes(manifest, spine, metadata, context)
    handle_routes(routes, context)


class IntOrTocType(click.ParamType):
    name = 'integer or "toc"'

    def convert(self, value, param, ctx):
        try:
            i = int(value)
        except ValueError:
            if value == 'toc':
                i = 0
            else:
                self.fail("Invalid argument, must be 'toc' or a"
                          " number greater than 0")
        else:
            if i < 1:
                self.fail("Numbers must be greater than 0")
        return i


def make_order(ctx, param, values):
    if len(values) == 0:
        return None
    filled_values = it.chain(
        values[:],
        (i for i in it.count() if i not in values)
    )
    return filled_values


webpub_epilog = """The --spine-order and --toc-order are specified multiple times to
determine the order. For example, '-o 2 -o toc -o 1' first puts the
second document, then the generated Table of Contents, then the first
document. The order defaults to '-o toc -o 1 -o 2 ...'.
"""

templates_path = os.path.join(os.path.dirname(__file__), 'templates')


@click.command(epilog=webpub_epilog)
@click.option('--directory', '-d', 'output_dir', metavar='DIR',
              type=click.Path(dir_okay=True, file_okay=False, writable=True),
              default='_result',
              help="Output directory (defaults to ./_result/)")
@click.option('--template', metavar='TEMPLATE',
              type=click.Path(dir_okay=False, file_okay=True, readable=True),
              default='default_template.html',
              help="The template HTML file in which the content is"
              " inserted for each section (defaults to"
              " {}/default_template.html).".format(templates_path))
@click.option('--spine-order', '-o', metavar='N', type=IntOrTocType(),
              default=None, multiple=True, callback=make_order,
              help="Reorder the chapter order for next/previous"
              " buttons. Input must be a positive number or the"
              " value 'toc' (for 'table of contents').")
@click.option('--toc-order', '-t', metavar='N', type=IntOrTocType(),
              default=None, multiple=True, callback=make_order,
              help="Reorder the order of the entries in the table of"
              " contents. Input is specified in the same way as with"
              " --spine-order. The default value, if unspecified, is"
              " inherited from --spine-order.")
@click.argument('epub_filename', metavar='INFILE',
                type=click.File('rb'))
@click.pass_context
def main(context, output_dir, template, spine_order, toc_order, epub_filename):
    """Process EPUB documents for web publishing.

    Given INFILE as input, this script:

    \b
    1. routes internal links
    2. adds cross-references to suttas
    3. generates a Table of Contents
    """
    if spine_order is None:
        spine_order = it.count()
    if toc_order is None:
        spine_order, toc_order = it.tee(spine_order)
        context.params['spine_order'] = spine_order
        context.params['toc_order'] = toc_order
    with zf.ZipFile(epub_filename) as epub_zip:
        make_webbook(context, epub_zip)


@click.command()
@click.option('--fallback-url', '-u', metavar="URL",
              help="Test against this URL if the internal link is not found"
              " locally. If the URL points to a resource (i.e. does not 404),"
              " this link won't be fixed. Useful if you have a relative link"
              " to a file on a server to which the given files are uploaded.")
@click.option('--dry-run', '-n', default=False, is_flag=True,
              help="Don't write anything, only show what would happen.")
@click.option('--basedir', '-b', metavar="PATH", default='',
              help="Base directory that all links share. All given files are"
              " pretended to be in this non-existing subdirectory of the common"
              " root directory that they're in.")
@click.option('--route', '-r', 'custom_routes', type=(str, str), multiple=True,
              metavar="<PATH PATH> ...",
              help="Specifies a custom route. Expects two arguments, and may"
              " be used multiple times.")
@click.option('--directory', '-d', 'output_dir', default="./",
              type=click.Path(file_okay=False, dir_okay=True,
                              writable=True, exists=True),
              help="The output directory to save the files.")
@click.option('--overwrite/--no-overwrite', '-f/ ', default=False,
              help="Whether or not to overwrite the given files. If not, the"
              " files are saved with a '.new' extension applied.")
@click.argument('filenames', metavar='INFILE', nargs=-1, required=True,
                type=click.Path(file_okay=True, dir_okay=False,
                                readable=True, writable=True, exists=True))
def linkfix(fallback_url, dry_run, basedir, custom_routes, output_dir, overwrite,
            filenames):
    """Attempts to fix relative links among the given files.
    """
    if dry_run:
        print("Dry run; no files will be written")
    routes = {}
    filenames = [os.path.realpath(fname) for fname in filenames]
    root_dir = os.path.commonpath(filenames)
    for fname in filenames:
        basename = os.path.basename(fname)
        old_path = os.path.join(root_dir, os.path.join(basedir, basename))
        routes[old_path] = fname
    routes.update(dict(custom_routes))

    for filepath, curpath in routes.items():
        result = linkfix_document(
            routes, root_dir, filepath, curpath, fallback_url
        )

        if dry_run:
            continue

        if not overwrite:
            curpath = curpath + ".new"

        with open(os.path.join(output_dir, curpath), 'wb') as dst:
            dst.write(html.tostring(
                result,
                doctype='<!DOCTYPE html>',
                encoding='utf-8',
                pretty_print=True,
            ))


if __name__ == '__main__':
    main()
