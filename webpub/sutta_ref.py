from collections import namedtuple
import functools as ft
import bisect
import re

import html5_parser as html5
import lxml.sax
from lxml.builder import E
import lxml.etree
from xml.sax import ContentHandler
from inxs import Transformation, Rule, MatchesXPath
import requests

from webpub.handlers import handle_routes, ConstDestMimetypeRoute
from webpub.linkfix.check import check_link_against_fallback
from webpub.util import (
    guard_unchanged, guard_dry_run, guard_overwrite, tostring, write_out
)
from webpub.ui import echo, choice_prompt

# List to determine chapter numbers from Dhp references.
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


def _manual_insert(ref):
    link = input('Enter cross reference link to "{}": '.format(ref.full_match))
    return link


def dhp_reference(ref):
    text_num = int(ref.text)
    chapter_num = bisect.bisect_left(dhp_last_text_numbers, text_num) + 1

    return f'/suttas/KN/Dhp/Ch{chapter_num:02}.html#dhp{text_num:03}'


def _continue(*args, **kwargs):
    return None


def _insert(*args, **kwargs):
    # get_sutta_ref_url checks if True is returned, and returns URL
    # without checking it.
    return True


sutta_abbrev_urls = {
    'AN': '/suttas/AN/AN{subsection}{sep}{text}.html',
    'MN': '/suttas/MN/MN{text}.html',
    'SN': '/suttas/SN/SN{subsection}{sep}{text}.html',
    'DN': '/suttas/DN/DN{text:0>2}.html',
    'Dhp': dhp_reference,
    'Iti': '/suttas/KN/Iti/iti{text}.html',
    'Khp': '/suttas/KN/Khp/khp{text}.html',
    'Sn': '/suttas/KN/StNp/StNp{subsection}{sep}{text}.html',
    'Snp': '/suttas/KN/StNp/StNp{subsection}{sep}{text}.html',
    'Thag': '/suttas/KN/Thag/thag{subsection}{sep}{text}.html',
    'Thig': '/suttas/KN/Thig/thig{subsection}{sep}{text}.html',
    'Ud': '/suttas/KN/Ud/ud{subsection}{sep}{text}.html',
    'Mv': '/vinaya/Mv/Mv{numeral}.html#pts{subsection}{sep}{text}',
    'Cv': _continue,
    'Pr': _continue,
    'Pc': _continue,
    'NP': _continue,
    'Sg': _continue,
    'Sk': _continue,
}

sutta_ref_regex_template = \
    r"(?P<section>{})\s?"\
    r"(?P<numeral>[IXV]+)?[.:]?"\
    r"(?P<text_or_subsection>[0-9]+)[.:]?(?P<text>[0-9]+)?"\
    r"(?:[-–](?P<text_end>[0-9]+))?"  # Includes ranges of texts

sutta_ref_regex = sutta_ref_regex_template.format(
    '|'.join(sutta_abbrev_urls.keys())
)

ignored_elements = [ 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                     lxml.etree.Comment, lxml.etree.ProcessingInstruction ]

sutta_ref_choices = {
    'cont': ('continue without inserting a link', _continue),
    'ins': ('insert the broken link anyway', _insert),
    'manual': ('insert a different link manually', _manual_insert),
}

SuttaRef = namedtuple(
    'SuttaRef',
    ['full_match', 'section', 'subsection', 'numeral', 'text', 'sep']
)


def get_url_format_callable(ref):
    url_format = sutta_abbrev_urls.get(ref.section)
    if callable(url_format):
        return ft.partial(url_format, ref)
    return ft.partial(
        url_format.format, subsection=ref.subsection,
        numeral=ref.numeral, text=ref.text, sep=ref.sep
    )

def get_sutta_ref_url(ref, stats, session, fallback_url):
    url_format = get_url_format_callable(ref)
    url = url_format()
    message = "Sutta link not found"
    while url is not None:
        try:
            working, link = check_link_against_fallback(
                url, session, fallback_url
            )
        except ValueError:
            return url

        if working:
            return url

        echo("{}: {}".format(message, link))
        choice = choice_prompt(
            'What should I do?', 'Sutta not found, ',
            sutta_ref_choices, ref, stats
        )
        if choice is True:
            return url
        url = choice


def find_sutta_refs(text):
    """Returns pairs of references and the "tail text" between the end of
    the current reference and the next reference. Starts with a
    sentinel (i.e. `None`) with the text preceding the first
    reference. If no references are found, this function returns
    `(None, text)`.

    """
    tail_text = text
    latest_ref = None
    matches = re.finditer(sutta_ref_regex, text)
    offset = 0

    for matchobj in matches:
        full_match = matchobj.group(0)
        numeral = matchobj.group('numeral')
        section = matchobj.group('section')
        text = matchobj.group('text') \
            or matchobj.group('text_or_subsection')
        subsection = sep = ''

        start = matchobj.start() - offset
        end = matchobj.end() - offset

        preceding_text = tail_text[:start]

        yield latest_ref, preceding_text

        tail_text = tail_text[end:]

        if matchobj.group('text'):
            subsection = matchobj.group('text_or_subsection')
            sep = '_'

        latest_ref = SuttaRef(full_match, section, subsection, numeral, text, sep)

        offset += end
    yield latest_ref, tail_text


def crossref_text(text, stats, session, fallback_url):
    preceding_text = text

    ref_finder = find_sutta_refs(text)

    # Get sentinel with the text leading up to first crossref
    _, preceding_text = next(ref_finder)
    last_element = None
    ref_elements = []

    for ref, tail_text in ref_finder:
        url = get_sutta_ref_url(ref, stats, session, fallback_url)
        if url:
            stats.set_changed()
            last_element = E("a", ref.full_match, {'href': url, 'class': 'sutta-ref'})
            last_element.tail = ''
            ref_elements.append(last_element)
        else:
            last_element.tail += ref.full_match
        last_element.tail += tail_text

    return (preceding_text, ref_elements)


def crossref_element(element, stats, session, fallback_url):
    if element.text is not None:
        element.text, new_child_elements = crossref_text(element.text, stats, session, fallback_url)
        element.extend(new_child_elements)

    if element.tail is not None:
        new_tail, new_sibling_elements = crossref_text(element.tail, stats, session, fallback_url)
        # Temporarily set tail to None before adding siblings.
        element.tail = None
        for sibling in new_sibling_elements:
            element.addnext(sibling)
        element.tail = new_tail


def crossref_document(routes, filepath, currentpath, stats, fallback_url):
    with open(currentpath, mode='rb') as doc:
        doc_tree = html5.parse(doc.read(), fallback_encoding='utf-8')

    with requests.Session() as s:
        for element in doc_tree.find('body').iter():
            if element.tag in ignored_elements:
                continue
            crossref_element(element, stats, s, fallback_url)
        return doc_tree


crossref_mime_handlers = {
    'text/html': (crossref_document, guard_unchanged, guard_dry_run,
                  guard_overwrite, tostring, write_out),
    'application/xhtml+xml': 'text/html',
    '*/*': (),
}


class CrossRefRoute(ConstDestMimetypeRoute):
    def get_mime_to_handlers(self):
        return crossref_mime_handlers


def cross_ref_routes(filenames):
    for root_dir, src in filenames:
        yield CrossRefRoute(src, root_dir)


def cross_ref(filenames, fallback_url, dry_run, overwrite):
    context = {
        'dry_run': dry_run,
        'overwrite': overwrite,
        'output_dir': '.',
        'fallback_url': fallback_url,
    }
    routes = cross_ref_routes(filenames)
    handle_routes(routes, context)
