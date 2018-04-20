import os.path
from urllib.parse import urlparse, urlunparse

import webpub.util


def is_fallback_working(url, routed_cur_path):
    # Check if it exists on the filesystem
    routed_rel_dir = os.path.dirname(routed_cur_path)
    relpath = os.path.join(routed_rel_dir, url.path)
    if os.path.exists(relpath):
        return True
    return False


def get_route(routes, filedir, path):
    path = os.path.normpath(os.path.join(filedir, path))
    return routes.get(path)


def routed_url(filepath, routes, old_url_str, sourceline=None):
    url = urlparse(old_url_str)
    if webpub.util.is_relative(url):
        routed = get_route(routes, os.path.dirname(filepath), url.path)
        routed_cur_path = routes[filepath]
        if routed is None:
            if not is_fallback_working(url, routed_cur_path):
                webpub.ui.echo("{}:{} Broken and unfixable link found: {}".format(
                    os.path.relpath(filepath),
                    str(sourceline) + ':' if sourceline else '',
                    old_url_str,
                ))
            return old_url_str
        rel_routed = os.path.relpath(routed, os.path.dirname(routed_cur_path))

        if os.path.normpath(url.path) == rel_routed:
            return old_url_str

        url_list = list(url)
        url_list[2] = rel_routed
        new_url_str = urlunparse(url_list)
        webpub.ui.echo(
            "Routed {} to {}.".format(old_url_str, new_url_str),
            verbosity=2
        )
        return new_url_str
    return old_url_str


def route_url(routes, filepath, element, fallback_url=None):
    old_url = None
    try:
        attrib, old_url = webpub.util.matched_url(element)
    except ValueError:
        return element

    if webpub.util.is_absolute(old_url):
        return element

    element.attrib[attrib] = routed_url(
        filepath, routes, old_url, element.sourceline
    )
    return element
