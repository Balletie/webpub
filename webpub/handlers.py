from collections import OrderedDict
import dependency_injection
import mimetypes
import mimeparse
import os

from webpub.util import copy_out, echo


class Route(object):
    def __init__(self, src, mimetype=None):
        self.src = src
        self._mimetype = mimetype

    @property
    def dst(self):
        raise NotImplementedError()

    @property
    def handlers(self):
        raise NotImplementedError()

    @property
    def mimetype(self):
        return self._mimetype or mimetypes.guess_type(self.src)[0]


class IdentityRoute(Route):
    def __init__(self, src, dst, mimetype=None):
        super().__init__(src, mimetype)
        self._dst = dst

    @property
    def dst(self):
        return self._dst or os.path.basename(self.src)

    def handlers(self):
        return (copy_out,)


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

    @property
    def dst(self):
        dst, _handlers = self.get_handlers()

        if callable(dst):
            return dst(self.src)
        return os.path.join(dst, os.path.basename(self.src))

    @property
    def handlers(self):
        _dst, handlers = self.get_handlers()
        return handlers


class ConstDestMimetypeRoute(MimetypeRoute):
    def __init__(self, src, dst, mimetype=None):
        super().__init__(src, mimetype)
        self._dst = dst

    @property
    def dst(self):
        return self._dst

    @property
    def handlers(self):
        return self.get_handlers()


class AbortHandling(Exception):
    """Aborts handlers."""


class SkipHandler(Exception):
    """Skips the current handler and continues to the next one."""


def _apply_handlers(handlers, context):
    echo(
        "\nStart handling {}.".format(os.path.relpath(context['filepath'])),
        verbosity=1
    )
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
            print(str(e))
            break

    del context['input']


def handle_routes(routes, context):
    context.setdefault('routes', {})
    context.setdefault('src_to_title', {})
    handlers_with_input = OrderedDict()
    for route in routes:
        src = route.src
        handlers = route.handlers
        context['routes'][src] = route.dst
        handlers_with_input.setdefault(handlers, []).append(src)

    for handlers, srcs in handlers_with_input.items():
        for src in srcs:
            context['filepath'] = src
            context['currentpath'] = src
            context['section_title'] = context['src_to_title'].get(src, '')
            _apply_handlers(handlers, context)
