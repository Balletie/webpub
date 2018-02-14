def insert_into_template(context, root, template):
    head = root.find('head')
    body = root.find('body')
    template_head = template.find('head')
    template_content = template.get_element_by_id('content')
    template_head.extend(head.getchildren())
    template_content.extend(body.getchildren())


def insert_meta(template, section_title, meta_title, meta_author, elmaker):
    head = template.find('head')
    title = head.find('title')
    if title is not None:
        head.remove(title)
    head.insert(0, elmaker.title(section_title + ' | ' + meta_title))
    author_suffix = (' by ' + meta_author) if meta_author else ''
    head.insert(1, elmaker.meta(
        name='description', content=meta_title + author_suffix
    ))


def insert_prev_next(template, routes, filepath, toc_src, spine, elmaker):
    spine_index = spine.index(filepath)
    prev_src = spine[spine_index - 1] if spine_index > 0 else None
    next_src = spine[spine_index + 1] if spine_index < len(spine) - 1 else None

    container = elmaker.div(id="nextbutton")
    if prev_src:
        container.append(elmaker.a(
            elmaker.img(
                src="/images/actions/go-next-button2.png",
                title="Previous page"
            ),
            {'href': routes[prev_src], 'class': "next"}
        ))
    container.append(elmaker.a(
        elmaker.img(
            src="/images/actions/ToC_button.png",
            title="Table of Contents"
        ),
        {'href': routes[toc_src], 'class': "next"}
    ))
    if next_src:
        container.append(elmaker.a(
            elmaker.img(
                src="/images/actions/go-next-button2.png",
                title="Next page"
            ),
            {'href': routes[next_src], 'class': "next"}
        ))
    template_content = template.get_element_by_id('content')
    template_content.append(container)
