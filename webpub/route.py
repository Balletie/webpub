import os.path
from urllib.parse import urlparse, urlunparse


def is_relative(url):
    return not url.netloc and not url.scheme and url.path


def get_route(routes, filedir, path):
    path = os.path.normpath(os.path.join(filedir, path))

    return routes.get(path)


def routed_url(filepath, routes, root_dir, old_url_str):
    url = urlparse(old_url_str)
    if is_relative(url):
        routed = get_route(routes, os.path.dirname(filepath), url.path)
        routed_cur_path = routes[filepath]
        rel_routed = os.path.relpath(routed, os.path.dirname(routed_cur_path))
        url_list = list(url)
        url_list[2] = rel_routed
        new_url_str = urlunparse(url_list)
        print("Routed {} to {}.".format(old_url_str, new_url_str))
        return new_url_str
    return old_url_str


def route_url(routes, filepath, root_dir, element):
    old_url = None
    for attrib in ['href', 'src']:
        old_url = element.attrib.get(attrib)
        if old_url:
            break
    else:
        return element

    element.attrib[attrib] = routed_url(filepath, routes, root_dir, old_url)
    return element
