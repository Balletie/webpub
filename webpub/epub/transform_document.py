import os

import requests
import html5_parser as html5
from inxs import (
    lxml_utils, Rule, MatchesXPath, Transformation
)

from webpub.sutta_ref import (
    link_sutta_references, sutta_ref_xpath, add_re_namespace
)
from webpub.route import route_url
from webpub.util import has_link


def remove_from_tree(element):
    lxml_utils.remove_elements(element)


def transform_document(routes, root_dir, epub_zip, filepath, currentpath,
                       fallback_url):
    context = locals().copy()
    context.pop('epub_zip', None)

    transformation = Transformation(
        add_re_namespace,
        Rule("title", remove_from_tree),
        Rule(has_link, route_url),
        Rule(MatchesXPath(sutta_ref_xpath), link_sutta_references),
        context=context,
    )

    with epub_zip.open(os.path.join(root_dir, filepath)) as doc_xml:
        doc_tree = html5.parse(doc_xml.read(), fallback_encoding='utf-8')

    with requests.Session() as s:
        return transformation(doc_tree, session=s)


transform_document.verbose_name = "Apply transformations"
