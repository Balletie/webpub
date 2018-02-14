import os.path

from lxml import html
from inxs import Rule, Any, MatchesAttributes, Transformation
import inxs.lib

from .route import route_url
from .transform import insert_into_template, insert_meta, insert_prev_next


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
        insert_into_template,
        insert_meta,
        insert_prev_next,
        context=context,
        result_object='context.template'
    )

    print("Transforming {}".format(filepath))
    with epub_zip.open(os.path.join(root_dir, filepath)) as doc_xml:
        doc_tree = html.parse(doc_xml)

    root = doc_tree.getroot()
    result = transformation(root)

    return result.getroottree()
