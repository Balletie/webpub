import functools as ft
import os.path
import requests
from urllib.parse import urlparse, urlunparse, urljoin
import click

import inxs.lxml_utils

import webpub.util


def _ensure_url(f):
    @ft.wraps(f)
    def wrapped(url_str):
        if isinstance(url_str, str):
            return f(urlparse(url_str))
        return f(url_str)
    return wrapped


@_ensure_url
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


def routed_url(filepath, routes, root_dir, v, old_url_str, fallback_url=None):
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
        webpub.util.echo(
            "Routed {} to {}.".format(old_url_str, new_url_str),
            v, 2
        )
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


def _ignore(element, attrib, context):
    return None


def _remove(element, attrib, context):
    inxs.lxml_utils.remove_elements(
        element, keep_children=True, preserve_text=True, preserve_tail=True
    )
    return None


def _insert_new(element, attrib, context):
    new_url = click.prompt('Enter new link')
    element.attrib[attrib] = new_url
    return element


def _apply_to_all(element, attrib, context):
    context.apply_to_all = True
    prev_action = link_choices.get(context.choice, ('', _ignore))
    return prev_action[1](element, attrib, context)


link_choices = {
    '1': ('ignore', _ignore),
    '2': ('remove link', _remove),
    '3': ('insert new link', _insert_new),
    'a': ('apply to all', _apply_to_all),
}


def choice_prompt(prompt, apply_all_msg, choices, element, attrib, context,
                  default='1'):
    choice = click.Choice(list(choices.keys()))
    choices_prompt = ', '.join(
        k + ': ' + v for k, (v, _) in choices.items()
    )

    default = context.choice or default
    value = default
    if not context.apply_to_all:
        value = click.prompt(
            '{}\n({})'.format(prompt, choices_prompt),
            default=default, type=choice,
        )
    else:
        click.echo(apply_all_msg + choices.get(value, ('', None))[0])
    res = choices.get(value, ('', _ignore))[1](element, attrib, context)
    if not context.apply_to_all:
        context.choice = value
    return res


def check_and_fix_absolute(element, session, context, verbosity,
                           currentpath, fallback_url=None):
    old_url = None
    try:
        attrib, old_url = _matched_url(element)
    except ValueError:
        return element

    if not is_absolute(old_url):
        return element

    message = "In file {}:\nBroken link".format(os.path.relpath(currentpath))
    while element is not None:
        old_url = element.attrib[attrib]
        old_url = urlparse(old_url)

        link = fallback_url

        if fallback_url is None:
            return element
        elif is_path(fallback_url):
            new_path = os.path.normpath(fallback_url + old_url.path)
            webpub.util.echo(
                "Checking link: {}".format(new_path),
                verbosity, 2
            )
            if os.path.exists(new_path):
                return element
            link = new_path
        else:
            check_url = urljoin(fallback_url, old_url.path)
            webpub.util.echo(
                "Checking link: {}".format(check_url),
                verbosity, 2
            )
            response = session.head(check_url, allow_redirects=True)
            if response.status_code == requests.codes.ok:
                return element
            link = check_url

        webpub.util.echo(
            "\n{}: {}\n".format(message, link),
            verbosity
        )
        element = choice_prompt(
            "Link is broken, what should I do?", "Link is broken, ",
            link_choices, element, attrib, context
        )
        message = "That link is also broken"


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


def route_url(routes, filepath, root_dir, element, verbosity,
              fallback_url=None):
    old_url = None
    try:
        attrib, old_url = _matched_url(element)
    except ValueError:
        return element

    if is_absolute(old_url):
        return element

    element.attrib[attrib] = routed_url(
        filepath, routes, root_dir, verbosity, old_url, fallback_url,
    )
    return element
