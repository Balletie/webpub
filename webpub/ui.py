import click


def choice_prompt(prompt, apply_all_msg, choices, context, *args, **kwargs):
    choice = click.Choice(list(choices.keys()))
    choices_prompt = ', '.join(
        k + ': ' + v for k, (v, _) in choices.items()
    )

    default = context.choice or '1'
    value = default
    if not context.apply_to_all:
        value = click.prompt(
            '{}\n({})'.format(prompt, choices_prompt),
            default=default, type=choice,
        )
    else:
        click.echo(apply_all_msg + choices[value][0])
    res = choices[value][1](context, *args, **kwargs)
    if not context.apply_to_all:
        context.choice = value
    return res


def echo(message="", verbosity=0):
    ui_ctx = click.get_current_context().find_object(
        UserInterfaceContext
    )
    if ui_ctx.verbosity >= verbosity:
        click.echo(message)


class UserInterfaceContext(object):
    def __init__(self, verbosity=0, choice=None, no_confirm=False):
        self.verbosity = verbosity
        self.choice = choice
        self.no_confirm = no_confirm
