from collections import namedtuple
import os.path

from lxml import etree
from inxs import Rule, Any, MatchesAttributes, Transformation
import inxs.lib

from .args import args, reorder
from .route import route_url
from .transform import insert_meta, insert_prev_next


def set_titles(element, src_to_title):
    src = element.xpath('./content/@src', smart_prefix=True)[0]
    title = element.xpath('./navLabel/text', smart_prefix=True)[0].text
    src_to_title[src] = title


def make_toc_skeleton(template, routes, section_title, elmaker):
    head = template.find('head')
    # Add styles to template
    for routed_item in routes.values():
        if routed_item.endswith('.css'):
            head.append(elmaker.link(
                href=routed_item, rel="stylesheet", type="text/css"
            ))

    # Add ToC list to content div
    content_div = template.get_element_by_id('content')
    content_child = elmaker.div(
        elmaker.h1(section_title),
        id='contents',
    )
    content_div.append(content_child)


TocEntry = namedtuple('TocEntry', ['title', 'href', 'children'])


def make_toc_tree(root):
    entries = []
    for np in root.xpath('./navPoint', smart_prefix=True):
        title = np.xpath('./navLabel/text', smart_prefix=True)[0].text
        href = np.xpath('./content/@src', smart_prefix=True)[0]
        entries.append(TocEntry(title, href, make_toc_tree(np)))
    return entries


def make_toc(root, filepath, routes, elmaker):
    root = root.xpath('./navMap', smart_prefix=True)[0]
    toc_self_entry = TocEntry('Table of Contents', routes[filepath], [])
    toc_entries = [toc_self_entry] + make_toc_tree(root)
    return reorder(toc_entries, args.toc_order)


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


def list_contents(previous_result, template, elmaker):
    contents_div = template.get_element_by_id('contents')
    contents_div.extend(toc_tree_to_html(previous_result, elmaker))


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


def transform_toc(routes, spine, toc_src, src_to_title, root_dir, epub_zip,
                  filepath, section_title, meta_title, meta_author, template):
    context = locals().copy()
    context.pop('epub_zip', None)

    transformation = Transformation(
        inxs.lib.init_elementmaker(
            name='elmaker',
        ),
        make_toc_skeleton,
        insert_meta,
        insert_prev_next,
        Rule('navPoint', set_titles),
        Rule(
            Any(MatchesAttributes({'href': None}),
                MatchesAttributes({'src': None}),),
            route_url,
        ),
        make_toc,
        list_contents,
        indent,
        result_object='context.template',
        context=context
    )

    print("Transforming {}".format(filepath))
    with epub_zip.open(os.path.join(root_dir, filepath)) as doc_xml:
        parser = etree.XMLParser(remove_blank_text=True)
        doc_tree = etree.parse(doc_xml, parser)

    root = doc_tree.getroot()
    result = transformation(root, src_to_title=src_to_title)

    return result.getroottree()
