from collections import namedtuple
import os.path

from lxml import etree
from inxs import Rule, Any, MatchesAttributes, Transformation
import inxs.lib

from webpub.route import route_url, routed_url
from webpub.util import reorder

ncx_namespace = {
    'ncx': "http://www.daisy.org/z3986/2005/ncx/",
}


def set_titles(element, src_to_title):
    src = element.xpath('./ncx:content/@src', namespaces=ncx_namespace)[0]
    title = element.xpath('./ncx:navLabel/ncx:text',
                          namespaces=ncx_namespace)[0].text
    src_to_title[src] = title


def make_toc_skeleton(context, filepath, routes, section_title, elmaker):
    context.html = elmaker.html(
        elmaker.head(*[
            elmaker.link(
                href=routed_url(filepath, routes, item),
                rel="stylesheet", type="text/css"
            )
            for item in routes.keys() if item.endswith('.css')
        ]),
        elmaker.body(
            elmaker.div(
                elmaker.h1(section_title),
                id='contents',
            )
        )
    )
    context.contents_div = context.html.xpath('//*[@id="contents"]')[0]


TocEntry = namedtuple('TocEntry', ['title', 'href', 'children'])


def make_toc_tree(root):
    entries = []
    for np in root.xpath('./ncx:navPoint', namespaces=ncx_namespace):
        title = np.xpath('./ncx:navLabel/ncx:text',
                         namespaces=ncx_namespace)[0].text
        href = np.xpath('./ncx:content/@src', namespaces=ncx_namespace)[0]
        entries.append(TocEntry(title, href, make_toc_tree(np)))
    return entries


def make_toc(root, toc_order, filepath, routes, elmaker):
    root = root.xpath('./ncx:navMap', namespaces=ncx_namespace)[0]
    toc_self_entry = TocEntry(
        'Table of Contents',
        routed_url(filepath, routes, filepath),
        []
    )
    toc_entries = [toc_self_entry] + make_toc_tree(root)
    return reorder(toc_entries, toc_order)


def toc_tree_to_html(previous_result, elmaker, level=0):
    ul = elmaker.ul
    li = elmaker.li
    a = elmaker.a
    children = list()
    for entry in previous_result:
        child = li(
            a(entry.title, href=entry.href),
            *toc_tree_to_html(entry.children, elmaker, level=level + 1)
        )
        children.append(child)
    if children:
        extra_kwargs = {}
        if level == 0:
            extra_kwargs = {"class": "no-ind"}
        toc = ul(*children, **extra_kwargs)
        return [toc]
    return []


def list_contents(previous_result, contents_div, elmaker):
    contents_div.extend(toc_tree_to_html(previous_result, elmaker))


def indent(contents_div, level=0):
    elem = contents_div
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def transform_toc(routes, toc_order, src_to_title, root_dir, epub_zip,
                  section_title, filepath):
    context = locals().copy()
    context.pop('epub_zip', None)
    context.pop('toc_order', None)

    transformation = Transformation(
        inxs.lib.init_elementmaker(
            name='elmaker',
        ),
        make_toc_skeleton,
        Rule('navPoint', set_titles),
        Rule(
            Any(MatchesAttributes({'href': None}),
                MatchesAttributes({'src': None}),),
            route_url,
        ),
        make_toc,
        list_contents,
        indent,
        result_object='context.html',
        context=context
    )

    with epub_zip.open(os.path.join(root_dir, filepath)) as doc_xml:
        parser = etree.XMLParser(remove_blank_text=True)
        doc_tree = etree.parse(doc_xml, parser)
    root = doc_tree.getroot()

    return transformation(
        root,
        src_to_title=src_to_title,
        toc_order=toc_order,
    )


transform_toc.verbose_name = "Generate Table of Contents"
