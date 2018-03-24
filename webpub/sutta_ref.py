import bisect
import re
import os

import html5lib as html5
import lxml.sax
from lxml import etree
from xml.sax import ContentHandler
from inxs import Transformation, Rule, MatchesXPath

from webpub.handlers import handle_routes, ConstDestMimetypeRoute
from webpub.util import guard_dry_run, guard_overwrite, tostring, write_out


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
        self.openElements = []
        super().__init__(*args, **kwargs)

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
    handler = SuttaRefContentHandler()
    tail = element.tail
    element.tail = None
    print(etree.tostring(element))
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


def crossref_document(routes, root_dir, filepath):
    context = locals().copy()

    transformation = Transformation(
        add_re_namespace,
        Rule(MatchesXPath(sutta_ref_xpath), link_sutta_references),
        context=context,
    )

    curpath = routes[filepath]
    print("Adding cross-references in {}".format(os.path.relpath(curpath)))
    with open(curpath) as doc:
        doc_tree = html5.parse(
            doc, treebuilder='lxml',
            namespaceHTMLElements=False
        )

    root = doc_tree.getroot()
    return transformation(root)


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
    for src in filenames:
        dst = src
        yield CrossRefRoute(src, dst)


def cross_ref(filenames, dry_run, output_dir, overwrite):
    if dry_run:
        print("Dry run; no files will be written")
    filenames = [os.path.realpath(fname) for fname in filenames]
    root_dir = os.path.commonpath(filenames)
    context = {
        'dry_run': dry_run,
        'overwrite': overwrite,
        'root_dir': root_dir,
        'output_dir': output_dir or root_dir,
    }
    routes = cross_ref_routes(filenames, output_dir)
    handle_routes(routes, context)
