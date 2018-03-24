import functools as ft
import os.path
import requests
from urllib.parse import urlparse, urlunparse, urljoin
import click

import inxs.lxml_utils


def _ensure_url(f):
    @ft.wraps(f)
    def wrapped(url_str):
        if isinstance(url_str, str):
            return f(urlparse(url_str))
        return f(url_str)
    return wrapped


def is_path(url):
    return not url.netloc and not url.scheme and url.path


@_ensure_url
def is_relative(url):
    return is_path(url) and not os.path.isabs(url.path)


@_ensure_url
def is_absolute(url):
    return is_path(url) and os.path.isabs(url.path)


def is_fallback_working(url, root_dir, routed_cur_path, fallback_base_url):
    # Check if it exists on the filesystem
    routed_rel_dir = os.path.dirname(routed_cur_path)
    relpath = os.path.join(routed_rel_dir, url.path)
    if os.path.exists(relpath):
        return True
    return False


def get_route(routes, filedir, path):
    path = os.path.normpath(os.path.join(filedir, path))

    return routes.get(path)


def routed_url(filepath, routes, root_dir, old_url_str, fallback_url=None):
    url = urlparse(old_url_str)
    if is_relative(url):
        routed = get_route(routes, os.path.dirname(filepath), url.path)
        routed_cur_path = routes[filepath]
        if routed is None:
            if not is_fallback_working(
                    url, root_dir, routed_cur_path, fallback_url):
                print("Broken and unfixable link found: {}".format(old_url_str))
            return old_url_str
        rel_routed = os.path.relpath(routed, os.path.dirname(routed_cur_path))

        if os.path.normpath(url.path) == rel_routed:
            return old_url_str

        url_list = list(url)
        url_list[2] = rel_routed
        new_url_str = urlunparse(url_list)
        print("Routed {} to {}.".format(old_url_str, new_url_str))
        return new_url_str
    return old_url_str


def _matched_url(element):
    url = None
    for attrib in ['href', 'src']:
        url = element.attrib.get(attrib)
        if url:
            return attrib, url
    else:
        raise ValueError("No URL attribute found on element")


def _ignore(element, attrib):
    return element


def _remove(element, attrib):
    inxs.lxml_utils.remove_elements(
        element, keep_children=True, preserve_text=True, preserve_tail=True
    )
    return element


def _insert_new(element, attrib):
    new_url = click.prompt('Enter new link')
    element[attrib] = new_url
    return element


link_choices = {
    '1': ('ignore', _ignore),
    '2': ('remove link', _remove),
    '3': ('insert new link', _insert_new),
}


def check_and_fix_absolute(element, session, fallback_url=None):
    old_url = None
    try:
        attrib, old_url = _matched_url(element)
    except ValueError:
        return element

    old_url = urlparse(old_url)

    if is_relative(old_url):
        return element

    if fallback_url is None:
        return element

    fallback_url = urljoin(fallback_url, old_url.path)
    print("Checking link: {}".format(fallback_url))
    response = session.head(fallback_url, allow_redirects=True)
    if response.status_code == requests.codes.ok:
        return element

    choice = click.Choice(list(link_choices.keys()))
    choices_prompt = ', '.join(
        k + ': ' + v for k, (v, _) in link_choices.items()
    )

    value = click.prompt(
        'Broken link, what should I do? ({})'.format(choices_prompt),
        default='1', type=choice,
    )
    return link_choices.get(value, _ignore)[1](element, attrib)


def has_relative_url(element, transformation):
    try:
        attrib, url = _matched_url(element)
        return is_relative(url)
    except ValueError:
        return False


def has_absolute_url(element, transformation):
    try:
        attrib, url = _matched_url(element)
        return is_absolute(url)
    except ValueError:
        return False


def route_url(routes, filepath, root_dir, element, fallback_url=None):
    old_url = None
    try:
        attrib, old_url = _matched_url(element)
    except ValueError:
        return element

    if is_absolute(old_url):
        return element

    element.attrib[attrib] = routed_url(
        filepath, routes, root_dir, old_url, fallback_url
    )
    return element
