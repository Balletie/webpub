import os
from urllib.parse import urlparse, urljoin, urldefrag

import requests
import click
import inxs.lxml_utils

import webpub.ui
import webpub.util


def _ignore(*args, **kwargs):
    return None


def _remove(ui_ctx, element, attrib):
    inxs.lxml_utils.remove_elements(
        element, keep_children=True, preserve_text=True, preserve_tail=True
    )
    return None


def _insert_new(ui_ctx, element, attrib):
    new_url = click.prompt('Enter new link')
    element.attrib[attrib] = new_url
    return element


def _apply_to_all(ui_ctx, element, attrib):
    ui_ctx.apply_to_all = True
    prev_action = link_choices.get(ui_ctx.choice, ('', _ignore))
    return prev_action[1](ui_ctx, element, attrib)


link_choices = {
    'keep': ('keep the (broken) link', _ignore),
    'rm': ('remove link', _remove),
    'subst': ('substitute the link with a different link', _insert_new),
}


def check_link_against_fallback(url_path, session, fallback_url=None):
    link = fallback_url
    if fallback_url is None:
        raise ValueError("Tried checking without fallback url")
    elif webpub.util.is_path(fallback_url):
        url_path = urldefrag(url_path).url
        new_path = os.path.normpath(fallback_url + '/' + url_path)
        link = new_path
        webpub.ui.echo(
            "Checking link: {}".format(new_path), verbosity=2
        )
        if os.path.exists(new_path):
            return True
    else:
        check_url = urljoin(fallback_url, url_path)
        link = check_url
        webpub.ui.echo(
            "Checking link: {}".format(check_url), verbosity=2
        )
        response = session.head(check_url, allow_redirects=True)
        if response.status_code == requests.codes.ok:
            return True
    return link


def check_and_fix_absolute(element, session, currentpath, fallback_url=None):
    old_url = None
    try:
        attrib, old_url = webpub.util.matched_url(element)
    except ValueError:
        return element

    if not webpub.util.is_absolute(old_url):
        return element

    message = "In file {}:\nBroken link".format(os.path.relpath(currentpath))
    while element is not None:
        old_url = element.attrib[attrib]
        old_url = urlparse(old_url)

        try:
            res = check_link_against_fallback(
                old_url.path, session, fallback_url
            )
        except ValueError:
            return element

        if res is True:
            return element
        link = res

        webpub.ui.echo("{}: {}".format(message, link))
        element = webpub.ui.choice_prompt(
            "Link is broken, what should I do?", "Link is broken, ",
            link_choices, element, attrib,
        )
        message = "That link is also broken"
