import os.path
import functools as ft

import cssutils

from .route import routed_url

cssutils.ser.prefs.keepUsedNamespaceRulesOnly = True
cssutils.ser.prefs.indentClosingBrace = False
cssutils.ser.prefs.omitLastSemicolon = False


def replace_urls(routes, filepath):
    stylesheet = cssutils.parseFile(filepath)
    cssutils.replaceUrls(
        stylesheet,
        ft.partial(routed_url, filepath, routes)
    )
    return stylesheet.cssText


def replace_urls_epub(epub_zip, routes, root_dir, filepath):
    style_string = epub_zip.read(os.path.join(root_dir, filepath))
    stylesheet = cssutils.parseString(style_string)
    cssutils.replaceUrls(
        stylesheet,
        ft.partial(routed_url, filepath, routes)
    )
    return stylesheet.cssText
