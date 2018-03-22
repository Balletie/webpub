import os.path
import requests
from urllib.parse import urlparse, urlunparse, urljoin


def is_relative(url):
    return not url.netloc and not url.scheme and url.path


def is_fallback_working(url, root_dir, routed_cur_path, fallback_base_url):
    # Check if it exists on the filesystem
    routed_rel_dir = os.path.dirname(routed_cur_path)
    relpath = os.path.join(routed_rel_dir, url.path)
    if os.path.exists(relpath):
        return True

    # As a last fallback, test for the base url
    if fallback_base_url is None:
        print("No fallback URL, stopping.")
        return False
    fallback_url = urljoin(fallback_base_url, url.path)
    print("Checking URL: {}".format(fallback_url))
    response = requests.head(fallback_url, allow_redirects=True)
    return response.status_code == requests.codes.ok


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


def route_url(routes, filepath, root_dir, element, fallback_url=None):
    old_url = None
    try:
        attrib, old_url = _matched_url(element)
    except ValueError:
        return element

    element.attrib[attrib] = routed_url(
        filepath, routes, root_dir, old_url, fallback_url
    )
    return element
