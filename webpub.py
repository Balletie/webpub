from collections import OrderedDict
import os
import os.path
import shutil
import functools as ft
import dependency_injection
import cssutils
from urllib.parse import urlparse, urlunparse
import mimeparse

from operator import itemgetter

from lxml import etree, html

from inxs import lib, lxml_utils, Rule, Any, MatchesAttributes, Transformation

import zipfile as zf

def generate_skeleton(context, e):
    context.html = e.html(
        e.head(e.title('Testing XML Example')),
        e.body(e.h1('Persons'), e.ul()))

def is_relative(url):
    return not url.netloc and not url.scheme

def get_route(routes, filedir, path):
    path = os.path.normpath(os.path.join(filedir, path))

    return routes.get(path)

def routed_url(filepath, routes, root_dir, old_url_str):
    url = urlparse(old_url_str)
    if is_relative(url):
        routed = get_route(routes, os.path.dirname(filepath), url.path)
        routed_cur_path = routes[filepath]
        rel_routed = os.path.relpath(routed, os.path.dirname(routed_cur_path))
        url_list = list(url)
        url_list[2] = rel_routed
        new_url_str = urlunparse(url_list)
        print("Routed {} to {}.".format(old_url_str, new_url_str))
        return new_url_str
    return old_url_str

def route_url(routes, filepath, root_dir, element):
    old_url = None
    for attrib in ['href', 'src']:
        old_url = element.attrib.get(attrib)
        if old_url:
            break
    else:
        return element

    element.attrib[attrib] = routed_url(filepath, routes, root_dir, old_url)
    return element

def insert_into_template(context, root, template):
    head = root.find('head')
    body = root.find('body')
    template_head = template.find('head')
    template_content = template.get_element_by_id('content')
    template_head.extend(head.getchildren())
    template_content.extend(body.getchildren())

def append_chapter_title(root, title):
    title_elem = root.find('head/title')
    title_elem.text = title + ' | ' + title_elem.text

def write_tree_out(input, filepath, routes):
    routed_path = os.path.join('_result', routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with open(routed_path, 'wb') as dst:
        input.write(
            dst,
            xml_declaration=True,
            encoding=input.docinfo.encoding,
            pretty_print=True,
        )

def copy_out(filepath, root_dir, routes):
    src_zip_path = os.path.join(root_dir, filepath)
    routed_path = os.path.join('_result', routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with epub_zip.open(src_zip_path, 'r') as src, open(routed_path, 'wb') as dst:
        shutil.copyfileobj(src, dst, 8192)

def replace_urls(routes, root_dir, filepath):
    style_string = epub_zip.read(os.path.join(root_dir, filepath))
    stylesheet = cssutils.parseString(style_string)
    cssutils.replaceUrls(stylesheet, ft.partial(routed_url, filepath, routes, root_dir))
    return stylesheet.cssText

def write_out(input, filepath, routes):
    routed_path = os.path.join('_result', routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with open(routed_path, 'wb') as dst:
        dst.write(input)

def transform_document(routes, root_dir, filepath, title, template):
    transformation = Transformation(
        Rule(
            Any(MatchesAttributes({'href': None}),
                MatchesAttributes({'src': None}),),
            route_url,
        ),
        append_chapter_title,
        insert_into_template,
        context=locals(),
        result_object='context.template'
    )

    print("Transforming {}".format(filepath))
    with epub_zip.open(os.path.join(root_dir, filepath)) as doc_xml:
        doc_tree = html.parse(doc_xml)

    root = doc_tree.getroot()
    result = transformation(root)

    return result.getroottree()

def set_titles(element, src_to_title):
    src = element.xpath('./content/@src', smart_prefix=True)[0]
    title = element.xpath('./navLabel/text', smart_prefix=True)[0].text
    src_to_title[src] = title

def make_toc_skeleton(template, elmaker):
    content_div = template.get_element_by_id('content')
    content_child = elmaker.div(
        elmaker.h1('Contents'),
        id='contents',
    )
    content_div.append(content_child)

def make_toc_tree(root, elmaker):
    ul = elmaker.ul
    li = elmaker.li
    a = elmaker.a
    children = list()
    for np in root.xpath('./navPoint', smart_prefix=True):
        title = np.xpath('./navLabel/text', smart_prefix=True)[0].text
        href = np.xpath('./content/@src', smart_prefix=True)[0]
        child = li(
            a(title, href=href),
            *make_toc_tree(np, elmaker)
        )
        children.append(child)
    if children:
        toc = ul(*children)
        return [toc]
    return []

def list_contents(root, template, elmaker):
    contents_div = template.get_element_by_id('contents')
    root = root.xpath('./navMap', smart_prefix=True)[0]
    contents_div.extend(make_toc_tree(root, elmaker))

def indent(template, level=0):
    i = "\n" + level*"  "
    if len(template):
        if not template.text or not template.text.strip():
            template.text = i + "  "
        if not template.tail or not template.tail.strip():
            template.tail = i
        for template in template:
            indent(template, level+1)
        if not template.tail or not template.tail.strip():
            template.tail = i
    else:
        if level and (not template.tail or not template.tail.strip()):
            template.tail = i

def transform_toc(routes, src_to_title, root_dir, filepath, template):
    transformation = Transformation(
        lib.init_elementmaker(
            name='elmaker',
        ),
        make_toc_skeleton,
        Rule('navPoint', set_titles),
        Rule(
            Any(MatchesAttributes({'href': None}),
                MatchesAttributes({'src': None}),),
            route_url,
        ),
        list_contents,
        indent,
        result_object='context.template',
        context=locals()
    )

    print("Transforming {}".format(filepath))
    with epub_zip.open(os.path.join(root_dir, filepath)) as doc_xml:
        parser = etree.XMLParser(remove_blank_text=True)
        doc_tree = etree.parse(doc_xml, parser)

    root = doc_tree.getroot()
    result = transformation(root, src_to_title=src_to_title)

    return result.getroottree()

def ensure(result, error_message):
    if not result:
        raise Exception(error_message)

    return result[0]

# Dict from mimetype media ranges to handlers and destination directory.
default_handlers = {
    'application/xhtml+xml': ('./', (transform_document, write_tree_out)),
    'application/x-dtbncx+xml': ('./', (transform_toc, write_tree_out)),
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

def handle_all(spine_refs, toc_ref, manifest, context):
    handlers_with_input = OrderedDict()

    toc_ref = ensure(toc_ref, "Spine section in EPUB package does not have a 'toc' attribute")
    toc_item = ensure(
        manifest.xpath('./item[@id=$ref]', ref=toc_ref, smart_prefix=True),
        "Couldn't find item in manifest for toc reference {} in spine section.".format(toc_ref),
    )
    context.setdefault('src_to_title', {toc_item.attrib['href']: 'Contents'})

    context.setdefault(
        'template',
        html.parse("./dhammatalks_site_template.html").getroot(),
    )
    context.setdefault('routes', {})
    for ref in [toc_ref] + spine_refs:
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
            context['title'] = context['src_to_title'].get(src, '')
            apply_handlers(handlers, context)

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

    context = { 'root_dir': root_dir }
    handle_all(spine_refs, toc_ref, manifest, context)

with zf.ZipFile('Five_Faculties_171022.epub') as epub_zip:
    make_webbook(epub_zip)
