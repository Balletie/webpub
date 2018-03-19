#!/usr/bin/env python
from collections import OrderedDict
import os
import os.path
import shutil
import dependency_injection

import mimeparse

from lxml import etree, html

import zipfile as zf

from webpub.args import args, reorder
from webpub.transform_document import transform_document
from webpub.transform_toc import transform_toc
from webpub.css import replace_urls


def write_tree_out(input, filepath, routes):
    routed_path = os.path.join(args.output_dir, routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with open(routed_path, 'wb') as dst:
        dst.write(html.tostring(
            input,
            doctype='<!DOCTYPE html>',
            encoding=input.docinfo.encoding,
            pretty_print=True,
        ))


def copy_out(epub_zip, filepath, root_dir, routes):
    src_zip_path = os.path.join(root_dir, filepath)
    routed_path = os.path.join(args.output_dir, routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with epub_zip.open(src_zip_path, 'r') as src:
        with open(routed_path, 'wb') as dst:
            shutil.copyfileobj(src, dst, 8192)


def write_out(input, filepath, routes):
    routed_path = os.path.join(args.output_dir, routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with open(routed_path, 'wb') as dst:
        dst.write(input)


def ensure(result, error_message):
    if not result:
        raise Exception(error_message)

    return result[0]


# Dict from mimetype media ranges to handlers and destination directory.
default_handlers = {
    'application/xhtml+xml': (lambda path: './' + os.path.basename(
        os.path.splitext(path)[0] + '.html'
    ),
                              (transform_document, write_tree_out)),
    'application/x-dtbncx+xml': (lambda _: './Contents.html',
                                 (transform_toc, write_tree_out)),
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
        manifest.xpath('./opf:item[@id=$ref]', ref=toc_ref, namespaces=opf_namespaces),
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

    context.setdefault(
        'template',
        html.parse(args.template).getroot(),
    )
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

    context['spine'] = reorder(context['spine'], args.spine_order)

    for manifest_item in manifest.xpath('./opf:item', namespaces=opf_namespaces):
        src, handlers = get_handlers(manifest_item, context)
        handlers_with_input.setdefault(handlers, []).append(src)

    for handlers, srcs in handlers_with_input.items():
        for src in srcs:
            context['filepath'] = src
            context['section_title'] = context['src_to_title'].get(src, '')
            apply_handlers(handlers, context)


def make_webbook(epub_zip):
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
        metadata = package_tree.xpath('/opf:package/opf:metadata', namespaces=opf_namespaces)
        manifest = package_tree.xpath('/opf:package/opf:manifest', namespaces=opf_namespaces)
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
    }
    handle_all(spine_refs, toc_ref, manifest, metadata, context)

def main():
    with zf.ZipFile(args.epub_filename) as epub_zip:
        make_webbook(epub_zip)

if __name__ == '__main__':
    main()
