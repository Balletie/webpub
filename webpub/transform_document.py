import bisect
import re
import os.path

import lxml.sax
from xml.sax import ContentHandler
import html5lib as html5
import requests
from inxs import lxml_utils, Rule, Any, MatchesAttributes, Transformation

from .route import (
    route_url, check_and_fix_absolute, has_relative_url, has_absolute_url
)


dhp_last_text_numbers = [
    20,
    32,
    43,
    59,
    75,
    89,
    99,
    115,
    128,
    145,
    156,
    166,
    178,
    196,
    208,
    220,
    234,
    255,
    272,
    289,
    305,
    319,
    333,
    359,
    382,
    423,
]


def manual_insert(full_match, numeral, text, sep, subsection):
    return input('Enter cross reference link to "{}": '.format(full_match))


def dhp_reference(full_match, numeral, text, sep, subsection):
    text_num = int(text)
    chapter_num = bisect.bisect_left(dhp_last_text_numbers, text_num) + 1

    return f'/suttas/KN/Dhp/Ch{chapter_num:02}.html#dhp{text_num:03}'


sutta_abbrev_urls = {
    'AN': '/suttas/AN/AN{subsection}{sep}{text}.html',
    'MN': '/suttas/MN/MN{text}.html',
    'SN': '/suttas/SN/SN{subsection}{sep}{text}.html',
    'DN': '/suttas/DN/DN{text}.html',
    'Dhp': dhp_reference,
    'Iti': '/suttas/KN/Iti/iti{text}.html',
    'Khp': '/suttas/KN/Khp/khp{text}.html',
    'Sn': '/suttas/KN/StNp/StNp{subsection}{sep}{text}.html',
    'Snp': '/suttas/KN/StNp/StNp{subsection}{sep}{text}.html',
    'Thag': '/suttas/KN/Thag/thag{subsection}{sep}{text}.html',
    'Thig': '/suttas/KN/Thig/thig{subsection}{sep}{text}.html',
    'Ud': '/suttas/KN/Ud/ud{subsection}{sep}{text}.html',
    'Mv': '/vinaya/Mv/Mv{numeral}.html#pts{subsection}{sep}{text}',
    'Cv': manual_insert,
    'Pr': manual_insert,
    'Pc': manual_insert,
    'NP': manual_insert,
    'Sg': manual_insert,
    'Sk': manual_insert,
}

sutta_ref_regex_template = \
    r"(?P<section>{})\s?"\
    r"(?P<numeral>[IXV]+)?[.:]?"\
    r"(?P<text_or_subsection>[0-9]+)[.:]?(?P<text>[0-9]+)?"\
    r"(?:[-–](?P<text_end>[0-9]+))?"  # Includes ranges of texts

sutta_ref_regex = sutta_ref_regex_template.format(
    '|'.join(sutta_abbrev_urls.keys())
)


class SuttaRefContentHandler(ContentHandler, object):
    def __init__(self, *args, **kwargs):
        self.out = lxml.sax.ElementTreeContentHandler()
        super().__init__(*args, **kwargs)

    def characters(self, data):
        after = data
        offset = 0

        matches = re.finditer(sutta_ref_regex, data)
        for matchobj in matches:
            full_match = matchobj.group(0)
            numeral = matchobj.group('numeral')
            section = matchobj.group('section')
            text = matchobj.group('text') \
                or matchobj.group('text_or_subsection')
            subsection = sep = ''

            if matchobj.group('text'):
                subsection = matchobj.group('text_or_subsection')
                sep = '_'

            start = matchobj.start() - offset
            end = matchobj.end() - offset

            before = after[:start]
            after = after[end:]

            self.out.characters(before)

            url_format = sutta_abbrev_urls.get(section)
            if callable(url_format):
                url = url_format(
                    full_match=full_match, numeral=numeral, text=text, sep=sep,
                    subsection=subsection
                )
            else:
                url = url_format.format(
                    numeral=numeral, text=text, sep=sep, subsection=subsection
                )

            self.out.startElement('a', {
                'href': url,
                'class': 'sutta-ref',
            })
            self.out.characters(full_match)
            self.out.endElement('a')

            offset += end
        self.out.characters(after)

    def startDocument(self, *args):
        self.out.startDocument(*args)

    def endDocument(self, *args):
        self.out.endDocument(*args)

    def startElement(self, *args):
        self.out.startElement(*args)

    def endElement(self, *args):
        self.out.endElement(*args)

    def startElementNS(self, *args):
        self.out.startElementNS(*args)

    def endElementNS(self, *args):
        self.out.endElementNS(*args)

    def getOutput(self):
        return self.out.etree.getroot()


def link_sutta_references(context, root):
    handler = SuttaRefContentHandler()
    lxml.sax.saxify(root.getroottree(), handler)
    out = handler.getOutput()
    old_body = root.find('body')
    new_body = out.find('body')
    root.replace(old_body, new_body)


def remove_from_tree(element):
    lxml_utils.remove_elements(element)


has_link = Any(MatchesAttributes({'href': None}),
               MatchesAttributes({'src': None}),)


def transform_document(routes, root_dir, epub_zip, filepath):
    context = locals().copy()
    context.pop('epub_zip', None)

    transformation = Transformation(
        Rule("title", remove_from_tree),
        Rule(has_link, route_url),
        link_sutta_references,
        context=context,
    )

    print("Transforming {}".format(filepath))
    with epub_zip.open(os.path.join(root_dir, filepath)) as doc_xml:
        doc_tree = html5.parse(
            doc_xml, treebuilder='lxml',
            default_encoding='utf-8', namespaceHTMLElements=False
        )

    root = doc_tree.getroot()
    return transformation(root)


def linkfix_document(routes, root_dir, filepath, fallback_url):
    context = locals().copy()
    context['apply_to_all'] = False
    context['choice'] = None

    transformation = Transformation(
        Rule([has_link, has_relative_url], route_url),
        Rule([has_link, has_absolute_url], check_and_fix_absolute),
        context=context,
    )

    curpath = routes[filepath]
    print("Fixing links in {}".format(os.path.relpath(curpath)))
    with open(curpath) as doc:
        doc_tree = html5.parse(
            doc, treebuilder='lxml',
            namespaceHTMLElements=False
        )

    root = doc_tree.getroot()
    with requests.Session() as s:
        return transformation(root, session=s)
