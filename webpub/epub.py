import os

from lxml import etree

from webpub.transform_document import transform_document
from webpub.transform_toc import transform_toc
from webpub.transform import render_template
from webpub.css import replace_urls
from webpub.handlers import handle_routes, MimetypeRoute
from webpub.util import reorder, ensure, copy_out, write_out


ocf_namespace = {
    'ocf': 'urn:oasis:names:tc:opendocument:xmlns:container',
}

opf_namespaces = {
    'opf': 'http://www.idpf.org/2007/opf',
    'dc': 'http://purl.org/dc/elements/1.1/',
}


def add_metadata(context, metadata):
    meta_title = metadata.xpath(
        './dc:title/text()',
        namespaces=opf_namespaces
    )
    meta_author = metadata.xpath(
        './dc:creator[@opf:role="aut"]/text()',
        namespaces=opf_namespaces
    )
    context.setdefault('meta_title', meta_title[0] if meta_title else '')
    context.setdefault('meta_author', meta_author[0] if meta_author else '')


def get_toc_item(spine, manifest):
    toc_ref = ensure(
        spine.xpath('./@toc', namespaces=opf_namespaces),
        "Spine section in EPUB package does not have a 'toc' attribute"
    )
    toc_item = ensure(
        manifest.xpath('./opf:item[@id=$ref]', ref=toc_ref,
                       namespaces=opf_namespaces),
        "Couldn't find item in manifest for toc reference {}"
        " in spine section.".format(toc_ref)
    )
    return toc_item


def _ensure_html_extension(path):
    return './' + os.path.basename(os.path.splitext(path)[0] + '.html')


# Dict from mimetype media ranges to handlers and destination directory.
default_mime_to_dst_and_handlers = {
    'text/html': (_ensure_html_extension,
                  (transform_document, render_template,
                   write_out)),
    'application/xhtml+xml': 'text/html',
    'application/x-dtbncx+xml': (lambda _: './Contents.html',
                                 (transform_toc, render_template,
                                  write_out)),
    'text/css': ('./css/', (replace_urls, write_out)),
    'image/*': ('./img/', (copy_out,)),
    '*/*': ('./etc/', (copy_out,))
}


class EpubMimetypeRoute(MimetypeRoute):
    def get_mime_to_handlers(self):
        return default_mime_to_dst_and_handlers


def epub_routes(manifest, spine, metadata, context):
    spine_refs = spine.xpath(
        './opf:itemref/@idref',
        namespaces=opf_namespaces
    )
    toc_item = get_toc_item(spine, manifest)
    toc_ref = toc_item.attrib['id']
    toc_src = toc_item.attrib['href']
    context.setdefault('src_to_title', {toc_src: 'Contents'})
    context.setdefault('routes', {})
    context.setdefault('spine', [])
    context.setdefault('toc_src', toc_src)

    add_metadata(context, metadata)

    for ref in [toc_ref] + spine_refs:
        manifest_item = manifest.xpath(
            './opf:item[@id=$ref]',
            ref=ref, namespaces=opf_namespaces
        )
        if not manifest_item:
            print(
                "Warning: couldn't find item in manifest"
                "for reference {} in spine section.".format(ref)
            )
            continue
        manifest_item = manifest_item[0]
        route = EpubMimetypeRoute(
            manifest_item.attrib['href'],
            manifest_item.attrib['media-type']
        )
        yield route
        context['spine'].append(route.src)
        manifest.remove(manifest_item)

    context['spine'] = reorder(context['spine'], context['spine_order'])

    remaining_items = manifest.xpath('./opf:item', namespaces=opf_namespaces)
    for manifest_item in remaining_items:
        yield EpubMimetypeRoute(
            manifest_item.attrib['href'],
            manifest_item.attrib['media-type']
        )


def make_webbook(cli_context, epub_zip):
    root_path = None
    with epub_zip.open('META-INF/container.xml') as container_xml:
        container_tree = etree.parse(container_xml)
        root_path = container_tree.xpath(
            '//ocf:container/ocf:rootfiles/ocf:rootfile/@full-path',
            namespaces=ocf_namespace)

    root_path = ensure(
        root_path,
        "No filepath found in 'META-INF/container.xml'"
    )
    root_dir = os.path.dirname(root_path)

    with epub_zip.open(root_path) as package_xml:
        package_tree = etree.parse(package_xml)
        metadata = package_tree.xpath(
            '/opf:package/opf:metadata',
            namespaces=opf_namespaces
        )
        manifest = package_tree.xpath(
            '/opf:package/opf:manifest',
            namespaces=opf_namespaces
        )
        spine = package_tree.xpath(
            '/opf:package/opf:spine',
            namespaces=opf_namespaces
        )

    metadata = ensure(metadata, "No metadata section found in EPUB package.")
    manifest = ensure(manifest, "No manifest section found in EPUB package.")
    spine = ensure(spine, "No spine section found in EPUB package.")

    context = {
        'root_dir': root_dir,
        'epub_zip': epub_zip,
        'spine_order': cli_context.params['spine_order'],
        'toc_order': cli_context.params['toc_order'],
        'template': cli_context.params['template'],
        'output_dir': cli_context.params['output_dir'],
    }
    routes = epub_routes(manifest, spine, metadata, context)
    handle_routes(routes, context)
