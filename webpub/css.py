import os.path
import functools as ft

import css_parser

from .route import routed_url

css_parser.ser.prefs.keepUsedNamespaceRulesOnly = True
css_parser.ser.prefs.indentClosingBrace = False
css_parser.ser.prefs.omitLastSemicolon = False


def replace_urls(routes, filepath):
    stylesheet = css_parser.parseFile(filepath)
    css_parser.replaceUrls(
        stylesheet,
        ft.partial(routed_url, filepath, routes)
    )
    return stylesheet.cssText


def replace_urls_epub(epub_zip, routes, root_dir, filepath):
    style_string = epub_zip.read(os.path.join(root_dir, filepath))
    stylesheet = css_parser.parseString(style_string)
    css_parser.replaceUrls(
        stylesheet,
        ft.partial(routed_url, filepath, routes)
    )
    return stylesheet.cssText
