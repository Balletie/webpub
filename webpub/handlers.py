from collections import OrderedDict
import dependency_injection


def _apply_handlers(handlers, context):
    print("Start handling {}.".format(context['filepath']))
    for handler in handlers:
        kwargs = dependency_injection.resolve_dependencies(
            handler, context
        ).as_kwargs
        print(" - {}".format(handler.__name__))
        context['input'] = handler(**kwargs)


def handle_routes(routes, context):
    handlers_with_input = OrderedDict()
    for route in routes:
        src = route.src
        handlers = route.handlers
        context['routes'][src] = route.dst
        handlers_with_input.setdefault(handlers, []).append(src)

    for handlers, srcs in handlers_with_input.items():
        for src in srcs:
            context['filepath'] = src
            context['section_title'] = context['src_to_title'].get(src, '')
            _apply_handlers(handlers, context)
