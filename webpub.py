import os
import os.path
import shutil
import functools as ft
import dependency_injection
from urllib.parse import urlparse, urlunparse
import mimeparse

from operator import itemgetter

from lxml import etree

from inxs import lib, lxml_utils, Rule, Any, MatchesAttributes, Transformation

import zipfile as zf

def generate_skeleton(context, e):
    context.html = e.html(
        e.head(e.title('Testing XML Example')),
        e.body(e.h1('Persons'), e.ul()))

def is_relative(url):
    return not url.netloc and not url.scheme

def get_route(routes, root_dir, path):
    path = os.path.normpath(os.path.join(root_dir, path))
    return routes.get(path)

def route_url(routes, root_dir, element):
    old_url = None
    for attrib in ['href', 'src']:
        old_url = element.attrib.get(attrib)
        if old_url:
            break
    url = urlparse(old_url)
    if is_relative(url):
        routed = get_route(routes, root_dir, url.path)
        url_list = list(url)
        url_list[2] = routed
        new_url = urlunparse(url_list)
        print("Routed {} to {}.".format(old_url, new_url))
        element.attrib[attrib] = new_url
    return element

def write_tree_out(input, filepath, routes):
    routed_path = os.path.join('_result', routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with open(routed_path, 'wb') as dst:
        input.write(
            dst,
            xml_declaration=True,
            encoding=input.docinfo.encoding,
            pretty_print=True
        )

def copy_out(filepath, root_dir, routes):
    src_zip_path = os.path.join(root_dir, filepath)
    routed_path = os.path.join('_result', routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with epub_zip.open(src_zip_path, 'r') as src, open(routed_path, 'wb') as dst:
        shutil.copyfileobj(src, dst, 8192)

replace_urls = lambda filepath: filepath
write_out = copy_out

def transform_document(routes, root_dir, filepath):
    transformation = Transformation(
        # TODO:
        # put transformed documents in correct template with SSIs.
        Rule(
            Any(MatchesAttributes({'href': None}),
                MatchesAttributes({'src': None}),),
            route_url,
        ),
        context=locals()
    )

    print("Transforming {}".format(filepath))
    with epub_zip.open(os.path.join(root_dir, filepath)) as doc_xml:
        doc_tree = etree.parse(doc_xml)

    result = transformation(doc_tree.getroot())

    return result.getroottree()

def ensure(result, error_message):
    if not result:
        raise Exception(error_message)

    return result[0]

# Dict from mimetype media ranges to handlers and destination directory.
default_handlers = {
    'application/xhtml+xml': ('./', (transform_document, write_tree_out)),
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
    context['routes'][manifest_item_path] = os.path.join(
        dst, os.path.basename(manifest_item_path)
    )

    return manifest_item_path, handlers

def handle_all(spine_refs, manifest, context):
    handlers_with_input = {}
    context.setdefault('routes', {})
    for ref in spine_refs:
        manifest_item = manifest.xpath('./item[@id=$ref]', ref=ref, smart_prefix=True)
        if not manifest_item:
            print(
                "Warning: couldn't find item in manifest"
                "for reference {} in spine section.".format(ref)
            )
            continue
        manifest_item = manifest_item[0]
        src, handlers = get_handlers(manifest_item, context)
        handlers_with_input.setdefault(handlers, []).append(src)
        manifest.remove(manifest_item)

    for manifest_item in manifest.xpath('./item', smart_prefix=True):
        src, handlers = get_handlers(manifest_item, context)
        handlers_with_input.setdefault(handlers, []).append(src)

    for handlers, srcs in handlers_with_input.items():
        for src in srcs:
            context['filepath'] = src
            apply_handlers(handlers, context)

def get_toc(toc_ref, manifest):
    toc_ref = ensure(toc_ref, "Spine section in EPUB package does not have a 'toc' attribute")
    manifest_item = manifest.xpath('./item[@id=$ref]', ref=toc_ref, smart_prefix=True)
    if not manifest_item:
        print("Warning: couldn't find item in manifest for toc reference {} in spine section.".format(ref))
    manifest_item = manifest_item[0]
    toc_path = manifest_item.attrib["href"]
    manifest.remove(manifest_item)

    return toc_path

def make_webbook(epub_zip):
    root_path = None
    with epub_zip.open('META-INF/container.xml') as container_xml:
        container_tree = etree.parse(container_xml)
        root_path = container_tree.xpath(
            '//container/rootfiles/rootfile/@full-path',
            smart_prefix=True)

    root_path = ensure(root_path, "No filepath found in 'META-INF/container.xml'")
    root_dir = os.path.dirname(root_path)

    with epub_zip.open(root_path) as package_xml:
        package_tree = etree.parse(package_xml)
        manifest = package_tree.xpath('/package/manifest', smart_prefix=True)
        spine_refs = package_tree.xpath('/package/spine/itemref/@idref', smart_prefix=True)
        toc_ref = package_tree.xpath('/package/spine/@toc', smart_prefix=True)

    manifest = ensure(manifest, "No manifest section found in EPUB package.")

    toc_path = get_toc(toc_ref, manifest)

    context = { 'root_dir': root_dir }
    handle_all(spine_refs, manifest, context)

with zf.ZipFile('Five_Faculties_171022.epub') as epub_zip:
    make_webbook(epub_zip)
