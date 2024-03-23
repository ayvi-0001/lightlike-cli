from __future__ import annotations

from inspect import cleandoc
from typing import TYPE_CHECKING, Sequence

import rich_click as click
from rich import print as rprint

from lightlike.app import _pass, render
from lightlike.app.client import (
    _select_credential_source,
    _select_project,
    get_client,
    reconfigure,
)
from lightlike.app.config import AppConfig
from lightlike.app.group import AliasedRichGroup, _RichCommand
from lightlike.cmd.query import query_repl
from lightlike.cmd.snapshot import snapshot
from lightlike.internal import markup, utils
from lightlike.internal.enums import ClientInitOptions, CredentialsSource
from lightlike.lib.third_party import _questionary

if TYPE_CHECKING:
    from google.cloud.bigquery.client import Project
    from rich.console import Console

__all__: Sequence[str] = ("bq",)


@click.group(
    cls=AliasedRichGroup,
    short_help="BigQuery client settings & commands.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def bq(debug: bool) -> None:
    """Command group for handling BigQuery Client configuration."""


bq.add_command(query_repl)
bq.add_command(snapshot)


@bq.command(
    cls=_RichCommand,
    name="init",
    short_help="Change active project or credentials source.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dim("Did not change configuration.")),
)
@_pass.console
def init(console: "Console") -> None:
    """Change active project or credentials source."""
    client = get_client()

    credentials = client._credentials
    if hasattr(credentials, "service_account_email"):
        account = credentials.service_account_email
    else:
        account = client.get_service_account_email(project=client.project)

    console.print(
        cleandoc(
            f"""
            Settings from your current configuration are:

            core:
              account: {account}
              project: {client.project}
              
            """
        )
    )

    option = _questionary.select(
        message="Pick an option:",
        choices=[
            ClientInitOptions.UPDATE_PROJECT % client.project,
            ClientInitOptions.UPDATE_AUTH,
        ],
    )

    if option == ClientInitOptions.UPDATE_PROJECT % client.project:
        project_id = _select_project(client)

        with AppConfig().update() as config:
            config["client"].update(active_project=project_id)

        reconfigure()

    elif option == ClientInitOptions.UPDATE_AUTH:
        source = _select_credential_source()

        match source:
            case CredentialsSource.from_service_account_key:
                with AppConfig().update() as config:
                    config["client"].update(credentials_source=source)

                reconfigure()

            case CredentialsSource.from_environment:
                with AppConfig().update() as config:
                    config["client"].update(
                        credentials_source=source, active_project=None
                    )

                reconfigure()


@bq.command(
    cls=_RichCommand,
    name="show",
    short_help="Show the current credentials object.",
)
@_pass.console
def show(console: "Console") -> None:
    """Show the current credentials object."""
    from rich._inspect import Inspect

    _inspect = Inspect(
        get_client()._credentials,
        help=True,
        methods=False,
        docs=True,
        private=False,
        dunder=False,
        sort=True,
        all=False,
        value=True,
    )

    console.print(
        _inspect,
        width=console.width,
        justify="center",
        new_line_start=True,
    )


@bq.command(
    cls=_RichCommand,
    name="projects",
    short_help="List client available projects.",
)
def projects() -> None:
    """List client available projects."""
    projects: Sequence["Project"] = list(get_client().list_projects())
    table = render.mappings_list_to_rich_table([vars(p) for p in projects])
    render.new_console_print(table)


@bq.group(
    name="reset",
    invoke_without_command=True,
    subcommand_metavar="",
    short_help="Reset client settings/auth.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dim("Did not change configuration.")),
)
@_pass.console
@click.pass_context
def reset(ctx: click.Context, console: "Console") -> bool:
    """Reset client settings/auth."""
    if ctx.invoked_subcommand is None:
        console.print(
            "This will remove any saved client settings and "
            "you will be asked to reconfigure client auth."
        )

        if _questionary.confirm(message="Continue?", auto_enter=True):
            with AppConfig().update() as config:
                config["user"].update(
                    password="null",
                    salt=[],
                    stay_logged_in=False,
                )
                config["client"].update(
                    active_project="null",
                    credentials_source=CredentialsSource.not_set,
                    service_account_key=[],
                )

            return True
    return False


@reset.result_callback()
def reset_callback(result: bool) -> None:
    if result is True:
        reconfigure()
