import os
from jinja2 import Environment, ChoiceLoader, PackageLoader, FileSystemLoader
from lxml import html


jinja2_env = Environment(
    loader=ChoiceLoader([
        FileSystemLoader(os.getcwd()),
        PackageLoader('webpub'),
    ]),
)


def render_template(template, input, filepath, spine,
                    routes, toc_src,
                    section_title, meta_title, meta_author):
    spine_index = spine.index(filepath)
    prev_src = spine[spine_index - 1] if spine_index > 0 else None
    next_src = spine[spine_index + 1] if spine_index < len(spine) - 1 else None
    context = {
        'prev_url': routes.get(prev_src, None) if prev_src else None,
        'next_url': routes.get(next_src, None) if next_src else None,
        'toc_url': routes.get(toc_src, None),
        'src': filepath,
        'meta_title': meta_title,
        'meta_author': meta_author,
        'section_title': section_title,
    }
    for tag in ('head', 'body'):
        context[tag] = ''.join(
            html.tostring(el, encoding='unicode')
            for el in input.find(tag).iterchildren()
        )
    template = jinja2_env.get_template(template)
    return template.render(context).encode()


render_template.verbose_name = "Apply template"
