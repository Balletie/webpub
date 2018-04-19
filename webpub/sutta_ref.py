from collections import namedtuple
import functools as ft
import bisect
import re

import html5lib as html5
import lxml.sax
from xml.sax import ContentHandler
from inxs import Transformation, Rule, MatchesXPath
import requests

from webpub.handlers import handle_routes, ConstDestMimetypeRoute
from webpub.route import check_link_against_fallback
from webpub.util import guard_dry_run, guard_overwrite, tostring, write_out
from webpub.ui import echo, choice_prompt


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


def _manual_insert(ui_context, ref):
    return input('Enter cross reference link to "{}": '.format(ref.full_match))


def dhp_reference(context, ref):
    text_num = int(ref.text)
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
    'Cv': _manual_insert,
    'Pr': _manual_insert,
    'Pc': _manual_insert,
    'NP': _manual_insert,
    'Sg': _manual_insert,
    'Sk': _manual_insert,
}

sutta_ref_regex_template = \
    r"(?P<section>{})\s?"\
    r"(?P<numeral>[IXV]+)?[.:]?"\
    r"(?P<text_or_subsection>[0-9]+)[.:]?(?P<text>[0-9]+)?"\
    r"(?:[-–](?P<text_end>[0-9]+))?"  # Includes ranges of texts

sutta_ref_regex = sutta_ref_regex_template.format(
    '|'.join(sutta_abbrev_urls.keys())
)


def _continue(ui_ctx, *args, **kwargs):
    return None


def _insert(ui_ctx, *args, **kwargs):
    # get_sutta_ref_url checks if True is returned, and returns URL
    # without checking it.
    return True


def _apply_to_all(ui_ctx, *args, **kwargs):
    ui_ctx.apply_to_all = True
    prev_action = sutta_ref_choices.get(ui_ctx.choice, ('', _continue))
    return prev_action[1](ui_ctx, *args, **kwargs)


sutta_ref_choices = {
    '1': ('continue without', _continue),
    '2': ('insert it anyway', _insert),
    '3': ('insert manually', _manual_insert),
}


SuttaRef = namedtuple(
    'SuttaRef',
    ['full_match', 'section', 'subsection', 'numeral', 'text', 'sep']
)


class SuttaRefContentHandler(ContentHandler, object):
    def __init__(self, context, *args, **kwargs):
        self.out = lxml.sax.ElementTreeContentHandler()
        self.context = context
        self.openElements = []
        super().__init__(*args, **kwargs)

    def get_url_format_callable(self, ref):
        url_format = sutta_abbrev_urls.get(ref.section)
        if callable(url_format):
            return ft.partial(url_format, self.context, ref)
        return ft.partial(
            url_format.format, subsection=ref.subsection,
            numeral=ref.numeral, text=ref.text, sep=ref.sep
        )

    def get_sutta_ref_url(self, ref):
        url_format = self.get_url_format_callable(ref)
        url = url_format()
        message = "In file {}:\nSutta link not found".format(
            self.context.currentpath
        )
        while url is not None:
            try:
                res = check_link_against_fallback(
                    url, self.context.session, self.context.fallback_url
                )
            except ValueError:
                return url

            if res is True:
                return url
            link = res

            echo("{}: {}".format(message, link))
            choice = choice_prompt(
                'What should I do?', 'Sutta not found, ',
                sutta_ref_choices, ref
            )
            if choice is True:
                return url
            url = choice
            message = "Sutta link not found"

    def characters(self, data):
        # If we're inside a link, don't substitute.
        if 'a' in self.openElements:
            self.out.characters(data)
            return

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
            ref = SuttaRef(full_match, section, subsection, numeral, text, sep)

            start = matchobj.start() - offset
            end = matchobj.end() - offset

            before = after[:start]
            after = after[end:]

            url = self.get_sutta_ref_url(ref)

            self.out.characters(before)
            if url:
                self.out.startElement('a', {
                    'href': url,
                    'class': 'sutta-ref',
                })
            self.out.characters(full_match)
            if url:
                self.out.endElement('a')

            offset += end
        self.out.characters(after)

    def startDocument(self, *args):
        self.out.startDocument(*args)

    def endDocument(self, *args):
        self.out.endDocument(*args)

    def startElement(self, *args):
        self.openElements.append(args[0])
        self.out.startElement(*args)

    def endElement(self, *args):
        assert self.openElements.pop() == args[0]
        self.out.endElement(*args)

    def startElementNS(self, *args):
        self.openElements.append(args[0][1])
        self.out.startElementNS(*args)

    def endElementNS(self, *args):
        assert self.openElements.pop() == args[0][1]
        self.out.endElementNS(*args)

    def getOutput(self):
        return self.out.etree.getroot()


def link_sutta_references(context, root, element):
    handler = SuttaRefContentHandler(context)
    tail = element.tail
    element.tail = None
    lxml.sax.saxify(element, handler)
    new_element = handler.getOutput()
    new_element.tail = tail
    element.getparent().replace(element, new_element)


sutta_ref_xpath = r'//body//*[not(self::a) and re:test(text(), "{}")]'.format(
    sutta_ref_regex
)


def add_re_namespace(xpath_evaluator):
    xpath_evaluator.register_namespace(
        're', 'http://exslt.org/regular-expressions'
    )


def crossref_document(routes, filepath, currentpath, fallback_url):
    context = locals().copy()

    transformation = Transformation(
        add_re_namespace,
        Rule(MatchesXPath(sutta_ref_xpath), link_sutta_references),
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


linkfix_mime_handlers = {
    'text/html': (crossref_document, guard_dry_run, guard_overwrite,
                  tostring, write_out),
    'application/xhtml+xml': 'text/html',
    '*/*': (),
}


class CrossRefRoute(ConstDestMimetypeRoute):
    def get_mime_to_handlers(self):
        return linkfix_mime_handlers


def cross_ref_routes(filenames, output_dir):
    for root_dir, src in filenames:
        yield CrossRefRoute(src, root_dir, output_dir)


def cross_ref(filenames, fallback_url, dry_run, output_dir, overwrite):
    if dry_run:
        print("Dry run; no files will be written")
    context = {
        'dry_run': dry_run,
        'overwrite': overwrite,
        'output_dir': output_dir,
        'fallback_url': fallback_url,
    }
    routes = cross_ref_routes(filenames, output_dir)
    handle_routes(routes, context)
