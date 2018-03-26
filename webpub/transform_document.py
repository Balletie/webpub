import os

import html5lib as html5
import requests
from inxs import (
    lxml_utils, Rule, Any, MatchesAttributes, MatchesXPath, Transformation
)

from .sutta_ref import link_sutta_references, sutta_ref_xpath, add_re_namespace
from .route import (
    route_url, check_and_fix_absolute, has_relative_url, has_absolute_url
)


def remove_from_tree(element):
    lxml_utils.remove_elements(element)


has_link = Any(MatchesAttributes({'href': None}),
               MatchesAttributes({'src': None}),)


def transform_document(routes, root_dir, epub_zip, filepath, verbosity,
                       currentpath, fallback_url):
    context = locals().copy()
    context.pop('epub_zip', None)
    context['apply_to_all'] = False
    context['choice'] = None

    transformation = Transformation(
        add_re_namespace,
        Rule("title", remove_from_tree),
        Rule(has_link, route_url),
        Rule(MatchesXPath(sutta_ref_xpath), link_sutta_references),
        context=context,
    )

    with epub_zip.open(os.path.join(root_dir, filepath)) as doc_xml:
        doc_tree = html5.parse(
            doc_xml, treebuilder='lxml',
            default_encoding='utf-8', namespaceHTMLElements=False
        )

    root = doc_tree.getroot()
    with requests.Session() as s:
        return transformation(root, session=s)


transform_document.verbose_name = "Apply transformations"


def linkfix_document(routes, root_dir, filepath, verbosity,
                     currentpath, fallback_url):
    currentpath = routes[filepath]
    context = locals().copy()
    context['apply_to_all'] = False
    context['choice'] = None

    transformation = Transformation(
        Rule([has_link, has_relative_url], route_url),
        Rule([has_link, has_absolute_url], check_and_fix_absolute),
        context=context,
    )

    with open(currentpath) as doc:
        doc_tree = html5.parse(
            doc, treebuilder='lxml',
            namespaceHTMLElements=False
        )

    root = doc_tree.getroot()
    with requests.Session() as s:
        return transformation(root, session=s)


linkfix_document.verbose_name = "Fix links"
