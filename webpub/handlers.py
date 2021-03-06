from collections import OrderedDict, ChainMap
import dependency_injection
import mimetypes
import mimeparse
import os

import click

from webpub.ui import echo
from webpub.stats import global_stats


class Route(object):
    def __init__(self, src, output_dir=None, mimetype=None):
        self.src = os.path.normpath(src)
        self.output_dir = output_dir
        self._mimetype = mimetype

    def get_dst(self):
        raise NotImplementedError()

    @property
    def dst(self):
        if self.output_dir is None:
            return self.get_dst()
        return os.path.normpath(os.path.join(self.output_dir, self.get_dst()))

    @property
    def handlers(self):
        raise NotImplementedError()

    @property
    def mimetype(self):
        return self._mimetype or mimetypes.guess_type(self.src)[0] or '*/*'


class MimetypeRoute(Route):
    def get_mime_to_handlers(self):
        raise NotImplementedError()

    def get_handlers(self):
        mimetype_handlers = self.get_mime_to_handlers()
        mime_match = mimeparse.best_match(
            mimetype_handlers.keys(), self.mimetype
        )
        str_or_tup = mimetype_handlers[mime_match]
        while isinstance(str_or_tup, str):
            str_or_tup = mimetype_handlers[str_or_tup]
        return str_or_tup

    def get_dst(self):
        dst, _handlers = self.get_handlers()

        if callable(dst):
            return dst(self.src)
        return os.path.join(dst, os.path.basename(self.src))

    @property
    def handlers(self):
        _dst, handlers = self.get_handlers()
        return handlers


class ConstDestMimetypeRoute(MimetypeRoute):
    def __init__(self, src, root_dir, output_dir=None, mimetype=None):
        if output_dir is None:
            output_dir = root_dir
        super().__init__(os.path.join(root_dir, src), output_dir, mimetype)
        self._dst = src

    def get_dst(self):
        return self._dst

    @property
    def handlers(self):
        return self.get_handlers()


class AbortHandling(Exception):
    """Aborts handlers."""

    def __init__(self, message, verbosity=0):
        super().__init__(message)

        self.verbosity = verbosity


class SkipHandler(Exception):
    """Skips the current handler and continues to the next one."""


def _apply_handlers(handlers, context):
    echo(click.style(os.path.relpath(context['filepath']), fg='yellow'))
    for handler in handlers:
        kwargs = dependency_injection.resolve_dependencies(
            handler, context
        ).as_kwargs

        handler_verbosity = getattr(handler, "verbosity", 1)
        handler_name = getattr(handler, "verbose_name", handler.__name__)
        echo("\n - {}".format(handler_name), verbosity=handler_verbosity)

        try:
            context['input'] = handler(**kwargs)
        except SkipHandler:
            continue
        except AbortHandling as e:
            echo(str(e), verbosity=e.verbosity)
            break

    context.pop('input', None)


def handle_routes(routes, context):
    context.setdefault('global_stats', global_stats)
    context.setdefault('routes', {})
    context.setdefault('src_to_title', {})
    handlers_with_input = OrderedDict()
    for route in routes:
        src = route.src
        handlers = route.handlers
        context['routes'][src] = route.dst
        handlers_with_input.setdefault(handlers, []).append(src)

    for handlers, srcs in handlers_with_input.items():
        if not handlers:
            continue
        for src in srcs:
            with global_stats.scope(src) as file_stats:
                local_context = {
                    'filepath': src,
                    'currentpath': src,
                    'section_title': context['src_to_title'].get(src, ''),
                    'stats': file_stats,
                }
                full_context = ChainMap(local_context, context)
                _apply_handlers(handlers, full_context)
