import os
import os.path
import shutil
import functools as ft
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

def set_result(context, root):
    context.result = root

def transform_document(context, doc):
    transformation = Transformation(
        # TODO:
        # put transformed documents in correct template with SSIs.
        Rule(
            Any(MatchesAttributes({'href': None}),
                MatchesAttributes({'src': None}),),
            route_url,
        ),
        set_result,
        result_object='context', context=context
    )

    print("Transforming {}".format(doc))
    with epub_zip.open(os.path.join(context['root_dir'], doc)) as doc_xml:
        doc_tree = etree.parse(doc_xml)

    new_context = transformation(doc_tree.getroot())
    context.update(new_context.__dict__)
    context[doc] = new_context.result.getroottree()

    return context

def ensure(result, error_message):
    if not result:
        raise Exception(error_message)

    return result[0]

# Dict from mimetype media ranges to destination directories.
mimetype_dest = {
    'application/xhtml+xml': './',
    'text/css': './css/',
    'image/*': './img/',
    '*/*': './etc/'
}

def route_manifest_item(routes, manifest_item):
    manifest_item_path = manifest_item.attrib["href"]
    manifest_mime = manifest_item.attrib["media-type"]
    dest_dir = mimetype_dest[mimeparse.best_match(mimetype_dest.keys(), manifest_mime)]
    routes[manifest_item_path] = os.path.join(dest_dir,
                                              os.path.basename(manifest_item_path))

def make_routes(spine_refs, manifest):
    doc_routes = {}
    for ref in spine_refs:
        manifest_item = manifest.xpath('./item[@id=$ref]', ref=ref, smart_prefix=True)
        if not manifest_item:
            print("Warning: couldn't find item in manifest for reference {} in spine section.".format(ref))
            continue
        manifest_item = manifest_item[0]
        route_manifest_item(doc_routes, manifest_item)
        manifest.remove(manifest_item)

    other_routes = {}
    for manifest_item in manifest.xpath('./item', smart_prefix=True):
        route_manifest_item(other_routes, manifest_item)

    return doc_routes, other_routes

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

    document_routes, other_routes = make_routes(spine_refs, manifest)

    print(document_routes)
    print(other_routes)
    routes = {}
    routes.update(document_routes)
    routes.update(other_routes)

    documents = document_routes.keys()
    context = { 'root_dir': root_dir, 'routes': routes }
    transformed_context = ft.reduce(
        transform_document,
        documents,
        context
    )

    for doc in documents:
        filename = os.path.join('_result', transformed_context['routes'][doc])
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, 'wb') as file_out:
            transformed_tree = transformed_context[doc]
            transformed_tree.write(
                file_out,
                xml_declaration=True,
                encoding=transformed_tree.docinfo.encoding,
                pretty_print=True
            )

    for zip_path, routed_path in other_routes.items():
        src_zip_path = os.path.join(root_dir, zip_path)
        dst_path = os.path.join('_result', routed_path)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

        with epub_zip.open(src_zip_path, 'r') as src, open(dst_path, 'wb') as dst:
            shutil.copyfileobj(src, dst, 8192)

with zf.ZipFile('Five_Faculties_171022.epub') as epub_zip:
    make_webbook(epub_zip)

