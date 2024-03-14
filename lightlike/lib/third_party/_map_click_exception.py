# mypy: disable-error-code="arg-type"
from typing import NoReturn, Sequence, cast

import rich_click as click
from rich.markup import render

from lightlike._console import CONSOLE_CONFIG
from lightlike.lib.third_party._rich_format_error import _rich_format_error

__all__: Sequence[str] = ("_map_click_exception",)


def _map_click_exception(e: click.ClickException) -> NoReturn:  # type: ignore
    """
    For click exceptions with additional parameters (param, param_hint, option_name, etc..),
    Errors are recreated first so that message can be properly formatted.
    Without this, the additional context of the errors (usage/hints/etc.) would not display.

    rich_click errors did not allow formatting of the message, so error messages are called to render() first.
    """
    match type(e):
        case click.MissingParameter:
            e = cast(click.MissingParameter, e)
            missing_parameter = click.MissingParameter(
                message=e.message,
                ctx=e.ctx,
                param=e.param,
                param_hint=e.param_hint,
            )
            message = render(
                missing_parameter.format_message(), style=CONSOLE_CONFIG.style
            )

            _rich_format_error(
                click.MissingParameter(
                    message=message,
                    ctx=e.ctx,
                    param=e.param,
                    param_hint=e.param_hint,
                ),
            )
        case click.BadOptionUsage:
            e = cast(click.BadOptionUsage, e)
            bad_option = click.BadOptionUsage(
                message=e.message,
                ctx=e.ctx,
                option_name=e.option_name,
            )
            message = render(
                bad_option.format_message(),
                style=CONSOLE_CONFIG.style,
            )

            _rich_format_error(
                click.BadOptionUsage(
                    message=message,
                    ctx=e.ctx,
                    option_name=e.option_name,
                ),
            )
        case click.BadParameter:
            e = cast(click.BadParameter, e)
            bad_parameter = click.BadParameter(
                message=e.message,
                ctx=e.ctx,
                param=e.param,
                param_hint=e.param_hint,
            )
            message = render(
                bad_parameter.format_message(),
                style=CONSOLE_CONFIG.style,
            )

            _rich_format_error(
                click.BadParameter(
                    message=message,
                    ctx=e.ctx,
                    param=e.param,
                    param_hint=e.param_hint,
                ),
            )
        case click.NoSuchOption:
            e = cast(click.NoSuchOption, e)
            no_such_option = click.NoSuchOption(
                option_name=e.option_name,
                message=e.message,
                possibilities=e.possibilities,
                ctx=e.ctx,
            )
            message = render(
                no_such_option.format_message(),
                style=CONSOLE_CONFIG.style,
            )

            _rich_format_error(
                click.NoSuchOption(
                    option_name=e.option_name,
                    message=message,
                    possibilities=e.possibilities,
                    ctx=e.ctx,
                ),
            )
        case click.UsageError:
            e = cast(click.UsageError, e)
            message = render(
                e.message,
                style=CONSOLE_CONFIG.style,
            )

            _rich_format_error(
                click.UsageError(
                    message=message,
                    ctx=e.ctx,
                ),
            )
        case click.BadArgumentUsage:
            e = cast(click.BadArgumentUsage, e)

            _rich_format_error(
                click.BadArgumentUsage(
                    message=render(
                        e.message,
                        style=CONSOLE_CONFIG.style,
                    ),
                    ctx=e.ctx,
                ),
            )
        case click.ClickException:
            message = render(
                e.message,
                style=CONSOLE_CONFIG.style,
            )
            _rich_format_error(
                click.ClickException(message=message),
            )
