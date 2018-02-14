import bisect
import re
import os.path

from lxml import html
import lxml.sax
from xml.sax import ContentHandler

from inxs import Rule, Any, MatchesAttributes, Transformation
import inxs.lib

from .route import route_url
from .transform import insert_into_template, insert_meta, insert_prev_next


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


def dhp_reference(text, sep, subsection):
    text_num = int(text)
    chapter_num = bisect.bisect_left(dhp_last_text_numbers, text_num) + 1

    return f'KN/Dhp/Ch{chapter_num:02}.html#dhp{text_num:03}'


sutta_abbrev_urls = {
    'AN': 'AN/AN{subsection}{sep}{text}.html',
    'MN': 'MN/MN{text}.html',
    'SN': 'SN/SN{text}.html',
    'DN': 'DN/DN{text}.html',
    'Dhp': dhp_reference,
    'Iti': 'KN/Iti/iti{text}.html',
    'Khp': 'KN/Khp/khp{text}.html',
    'Sn': 'KN/StNp/StNp{subsection}{sep}{text}.html',
    'Snp': 'KN/StNp/StNp{subsection}{sep}{text}.html',
    'Thag': 'KN/Thag/thag{subsection}{sep}{text}.html',
    'Thig': 'KN/Thig/thig{subsection}{sep}{text}.html',
    'Ud': 'KN/Ud/ud{subsection}{sep}{text}.html',
}

sutta_ref_regex_template = \
    r"(?P<section>{})\s?(?P<text_or_subsection>[0-9]+)[.:]?(?P<text>[0-9]+)?"\
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

            url_format = sutta_abbrev_urls.get(
                matchobj.group('section')
            )
            if callable(url_format):
                url = url_format(
                    text=text, sep=sep, subsection=subsection
                )
            else:
                url = url_format.format(
                    text=text, sep=sep, subsection=subsection
                )

            self.out.startElement('a', {
                'href': '/suttas/' + url
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


def transform_document(routes, spine, root_dir, epub_zip, filepath, toc_src,
                       section_title, meta_title, meta_author, template):
    context = locals().copy()
    context.pop('epub_zip', None)

    transformation = Transformation(
        inxs.lib.init_elementmaker(
            name='elmaker',
        ),
        Rule(
            Any(MatchesAttributes({'href': None}),
                MatchesAttributes({'src': None}),),
            route_url,
        ),
        link_sutta_references,
        insert_into_template,
        insert_meta,
        insert_prev_next,
        context=context,
        result_object='context.template',
    )

    print("Transforming {}".format(filepath))
    with epub_zip.open(os.path.join(root_dir, filepath)) as doc_xml:
        doc_tree = html.parse(doc_xml)

    root = doc_tree.getroot()
    result = transformation(root)

    return result.getroottree()
