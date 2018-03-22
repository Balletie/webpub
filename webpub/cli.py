#!/usr/bin/env python
from collections import OrderedDict
import itertools as it
import os
import os.path
import shutil
import zipfile as zf

import dependency_injection
import mimeparse
from lxml import etree, html
import click

from webpub.transform_document import transform_document, linkfix_document
from webpub.transform_toc import transform_toc
from webpub.transform import render_template
from webpub.css import replace_urls
from webpub.util import reorder


def copy_out(epub_zip, filepath, output_dir, root_dir, routes):
    src_zip_path = os.path.join(root_dir, filepath)
    routed_path = os.path.join(output_dir, routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with epub_zip.open(src_zip_path, 'r') as src:
        with open(routed_path, 'wb') as dst:
            shutil.copyfileobj(src, dst, 8192)


def write_out(input, filepath, output_dir, routes):
    routed_path = os.path.join(output_dir, routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with open(routed_path, 'wb') as dst:
        dst.write(input)


def ensure(result, error_message):
    if not result:
        raise Exception(error_message)

    return result[0]


def ensure_html_extension(path):
    return './' + os.path.basename(os.path.splitext(path)[0] + '.html')


# Dict from mimetype media ranges to handlers and destination directory.
default_handlers = {
    'application/xhtml+xml': (ensure_html_extension,
                              (transform_document, render_template,
                               write_out)),
    'application/x-dtbncx+xml': (lambda _: './Contents.html',
                                 (transform_toc, render_template,
                                  write_out)),
    'text/css': ('./css/', (replace_urls, write_out)),
    'image/*': ('./img/', (copy_out,)),
    '*/*': ('./etc/', (copy_out,))
}


def apply_handlers(handlers, context):
    print("Start handling {}.".format(context['filepath']))
    for handler in handlers:
        kwargs = dependency_injection.resolve_dependencies(
            handler, context
        ).as_kwargs
        print(" - {}".format(handler.__name__))
        context['input'] = handler(**kwargs)


def get_handlers(manifest_item, context, mimetype_handlers=default_handlers):
    manifest_item_path = manifest_item.attrib["href"]
    manifest_mime = manifest_item.attrib["media-type"]
    mime_match = mimeparse.best_match(mimetype_handlers.keys(), manifest_mime)

    dst, handlers = mimetype_handlers[mime_match]
    if not callable(dst):
        old_dst = dst

        def append_basename(path):
            return os.path.join(old_dst, os.path.basename(path))

        dst = append_basename

    dst = dst(manifest_item_path)
    context['routes'][manifest_item_path] = dst

    return manifest_item_path, handlers


ocf_namespace = {
    'ocf': 'urn:oasis:names:tc:opendocument:xmlns:container',
}

opf_namespaces = {
    'opf': 'http://www.idpf.org/2007/opf',
    'dc': 'http://purl.org/dc/elements/1.1/',
}


def handle_all(spine_refs, toc_ref, manifest, metadata, context):
    handlers_with_input = OrderedDict()

    toc_ref = ensure(
        toc_ref,
        "Spine section in EPUB package does not have a 'toc' attribute"
    )
    toc_item = ensure(
        manifest.xpath('./opf:item[@id=$ref]', ref=toc_ref,
                       namespaces=opf_namespaces),
        "Couldn't find item in manifest for toc reference {}"
        " in spine section.".format(toc_ref)
    )
    toc_src = toc_item.attrib['href']
    context.setdefault('src_to_title', {toc_src: 'Contents'})
    context.setdefault('routes', {})
    context.setdefault('spine', [])
    context.setdefault('toc_src', toc_src)
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
        src, handlers = get_handlers(manifest_item, context)
        context['spine'].append(src)
        handlers_with_input.setdefault(handlers, []).append(src)
        manifest.remove(manifest_item)

    context['spine'] = reorder(context['spine'], context['spine_order'])

    for manifest_item in manifest.xpath('./opf:item',
                                        namespaces=opf_namespaces):
        src, handlers = get_handlers(manifest_item, context)
        handlers_with_input.setdefault(handlers, []).append(src)

    for handlers, srcs in handlers_with_input.items():
        for src in srcs:
            context['filepath'] = src
            context['section_title'] = context['src_to_title'].get(src, '')
            apply_handlers(handlers, context)


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
        spine_refs = package_tree.xpath(
            '/opf:package/opf:spine/opf:itemref/@idref',
            namespaces=opf_namespaces
        )
        toc_ref = package_tree.xpath(
            '/opf:package/opf:spine/@toc',
            namespaces=opf_namespaces
        )

    metadata = ensure(metadata, "No metadata section found in EPUB package.")
    manifest = ensure(manifest, "No manifest section found in EPUB package.")

    context = {
        'root_dir': root_dir,
        'epub_zip': epub_zip,
        'spine_order': cli_context.params['spine_order'],
        'toc_order': cli_context.params['toc_order'],
        'template': cli_context.params['template'],
        'output_dir': cli_context.params['output_dir'],
    }
    handle_all(spine_refs, toc_ref, manifest, metadata, context)


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


@click.command(epilog=webpub_epilog)
@click.option('--directory', '-d', 'output_dir', metavar='DIR',
              type=click.Path(dir_okay=True, file_okay=False, writable=True),
              default='_result',
              help="Output directory (defaults to ./_result/)")
@click.option('--template', metavar='TEMPLATE',
              type=click.Path(dir_okay=False, file_okay=True, readable=True),
              default='default_template.html',
              help="The template HTML file in which the content is"
              " inserted for each section.")
@click.option('--spine-order', '-o', metavar='N', type=IntOrTocType(),
              default=it.count(), multiple=True, callback=make_order,
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
