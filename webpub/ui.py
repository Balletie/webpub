import click


class UserInterfaceContext(object):
    def __init__(self, verbosity=0, choice='1', apply_to_all=False):
        self.verbosity = verbosity
        self.choice = choice
        self.apply_to_all = apply_to_all


def get_ui_context():
    return click.get_current_context().find_object(
        UserInterfaceContext
    )


def choice_prompt(prompt, apply_all_msg, choices, *args, **kwargs):
    ui_ctx = get_ui_context()
    choice = click.Choice(list(choices.keys()))
    choices_prompt = ', '.join(
        k + ': ' + v for k, (v, _) in choices.items()
    )

    default = ui_ctx.choice
    value = default
    if not ui_ctx.apply_to_all:
        value = click.prompt(
            '{}\n({})'.format(prompt, choices_prompt),
            default=default, type=choice,
        )
    else:
        click.echo(apply_all_msg + choices[value][0])
    res = choices[value][1](ui_ctx, *args, **kwargs)
    if not ui_ctx.apply_to_all:
        ui_ctx.choice = value
    return res


def echo(message="", verbosity=0):
    ui_ctx = get_ui_context()
    if ui_ctx.verbosity >= verbosity:
        click.echo(message)