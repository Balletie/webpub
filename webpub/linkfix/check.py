import os
from urllib.parse import urlparse, urlunparse, urljoin, urldefrag

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


def _check_link_against_path_fallback(url_path, session, fallback_url):
    url_path = urldefrag(url_path).url
    new_path = os.path.normpath(fallback_url + '/' + url_path)
    webpub.ui.echo(
        "Checking path: {}".format(new_path), verbosity=2
    )
    if os.path.exists(new_path):
        return (True, new_path, "File exists")
    return (False, new_path, "File does not exist")


def _check_link_against_url_fallback(url_path, session, fallback_url):
    check_url = urljoin(fallback_url, url_path)
    webpub.ui.echo(
        "Checking URL: {}".format(check_url), verbosity=2
    )
    response = session.head(check_url, allow_redirects=True)
    msg = "Status code: " + str(response.status_code)
    if response.status_code == requests.codes.ok:
        return (True, check_url, msg)
    return (False, check_url, msg)


def check_link_against_fallback(url_path, session, fallback_url=None):
    link = fallback_url
    link_checker = _check_link_against_url_fallback
    msg = "N/A"

    if fallback_url is None:
        raise ValueError("Tried checking without fallback url")

    if webpub.util.is_path(fallback_url):
        link_checker = _check_link_against_path_fallback

    working, link, msg = link_checker(url_path, session, fallback_url)

    result_status = working and "OK   " or "ERROR"
    webpub.ui.echo("{status} {link} ({msg})".format(
        status=click.style(result_status, fg=working and 'green' or 'red'),
        link=link,
        msg=msg,
    ), verbosity=int(working))
    return (working, link)


def check_and_fix_link(element, session, currentpath, fallback_url=None):
    old_url = None
    try:
        attrib, old_url = webpub.util.matched_url(element)
    except ValueError:
        return element

    message = "At {}:{}".format(
        os.path.relpath(currentpath), element.sourceline
    )
    while element is not None:
        old_url = element.attrib[attrib]
        old_url = urlparse(old_url)

        if not webpub.util.is_path(old_url):
            return element

        if webpub.util.is_relative(old_url):
            fallback_url = os.path.dirname(currentpath)

        try:
            working, _link = check_link_against_fallback(
                old_url.path, session, fallback_url
            )
        except ValueError:
            return element

        if working:
            return element

        webpub.ui.echo("{}: {}".format(message, urlunparse(old_url)))
        element = webpub.ui.choice_prompt(
            "Link is broken, what should I do?", "Link is broken, ",
            link_choices, element, attrib,
        )
        message = "That link is also broken"
