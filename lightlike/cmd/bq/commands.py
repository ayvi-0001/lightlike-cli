import typing as t
from inspect import cleandoc

import click
from rich import print as rprint
from rich.table import Table

from lightlike.app import _questionary, render
from lightlike.app.client import (
    _select_credential_source,
    _select_project,
    get_client,
    reconfigure,
)
from lightlike.app.config import AppConfig
from lightlike.app.core import AliasedGroup, FormattedCommand, LazyAliasedGroup
from lightlike.cmd import _pass
from lightlike.internal import markup, utils
from lightlike.internal.enums import ClientInitOptions, CredentialsSource

if t.TYPE_CHECKING:
    from google.cloud.bigquery.client import Project
    from rich.console import Console

__all__: t.Sequence[str] = (
    "snapshot",
    "query",
    "init",
    "show",
    "projects",
    "reset",
)


@click.group(
    name="snapshot",
    cls=LazyAliasedGroup,
    lazy_subcommands={
        "create": "lightlike.cmd.bq.snapshot:create",
        "delete": "lightlike.cmd.bq.snapshot:delete",
        "list": "lightlike.cmd.bq.snapshot:list_",
        "restore": "lightlike.cmd.bq.snapshot:restore",
    },
    short_help="Create/restore snapshots.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def snapshot(debug: bool) -> None:
    """Create/restore snapshots."""


@click.command(
    cls=FormattedCommand,
    name="query",
    short_help="Start an interactive BQ shell.",
)
@_pass.console
def query(console: "Console") -> None:
    """Start an interactive BQ shell."""
    from lightlike.cmd.query import query_repl

    query_repl()


@click.command(
    cls=FormattedCommand,
    name="init",
    short_help="Change active project or credentials source.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not change configuration.")),
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

    credentials_source: CredentialsSource = AppConfig().get(
        "client", "credentials_source"
    )

    option = _questionary.select(
        message="Pick an option:",
        choices=[
            ClientInitOptions.UPDATE_PROJECT % client.project,
            ClientInitOptions.UPDATE_AUTH % credentials_source,
        ],
    )

    if option == ClientInitOptions.UPDATE_PROJECT % client.project:
        project_id = _select_project(client)

        with AppConfig().rw() as config:
            config["client"].update(active_project=project_id)

        reconfigure()

    elif ClientInitOptions.UPDATE_AUTH % credentials_source:
        source = _select_credential_source()

        match source:
            case CredentialsSource.from_service_account_key:
                with AppConfig().rw() as config:
                    config["client"].update(credentials_source=source)

                reconfigure()

            case CredentialsSource.from_environment:
                with AppConfig().rw() as config:
                    config["client"].update(
                        credentials_source=source, active_project=None
                    )

                reconfigure()


@click.command(
    cls=FormattedCommand,
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


@click.command(
    cls=FormattedCommand,
    name="projects",
    short_help="List available projects.",
)
@_pass.console
def projects(console: "Console") -> None:
    """List available projects."""
    projects: t.Sequence["Project"] = list(get_client().list_projects())
    table: Table = render.map_sequence_to_rich_table(
        mappings=[vars(p) for p in projects],
        string_ctype=["project_id", "friendly_name"],
        num_ctype=["numeric_id"],
    )
    if not table.row_count:
        rprint(markup.dimmed("No results"))
        raise click.exceptions.Exit

    console.print(table)


@click.group(
    cls=AliasedGroup,
    name="reset",
    invoke_without_command=True,
    subcommand_metavar="",
    short_help="Reset auth and all client settings.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not change configuration.")),
)
@_pass.console
@click.pass_context
def reset(ctx: click.Context, console: "Console") -> bool:
    """Reset auth and all client settings."""
    if ctx.invoked_subcommand is None:
        console.print(
            "This will remove any saved client settings and "
            "you will be asked to reconfigure client auth."
        )

        if _questionary.confirm(message="Continue?", auto_enter=True):
            with AppConfig().rw() as config:
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
    if result:
        reconfigure()
