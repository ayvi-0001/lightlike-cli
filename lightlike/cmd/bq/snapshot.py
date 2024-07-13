import typing as t

import click
from pytz import timezone
from rich import print as rprint
from rich.table import Table

from lightlike.app import _get, _questionary, dates, render, validate
from lightlike.app.config import AppConfig
from lightlike.app.core import FormattedCommand
from lightlike.cmd import _pass
from lightlike.internal import markup, utils

if t.TYPE_CHECKING:
    from datetime import datetime

    from google.cloud.bigquery import Client
    from rich.console import Console

    from lightlike.app.routines import CliQueryRoutines

__all__: t.Sequence[str] = ("snapshots",)


@click.command(
    cls=FormattedCommand,
    name="create",
    no_args_is_help=True,
    short_help="Create a snapshot.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not create snapshot.")),
)
@click.option(
    "-n",
    "--name",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Default format: timesheet_%Y-%m-%dT%H_%M_%S",
    required=True,
    default=None,
    callback=None,
    metavar=None,
    shell_complete=lambda c, p, i: [
        f"timesheet_{dates.now(timezone(AppConfig().get('settings', 'timezone'))).strftime('%Y-%m-%dT%H_%M_%S')}"
    ],
)
@click.option(
    "-e",
    "--expiration_timestamp",
    show_default=True,
    multiple=False,
    type=click.STRING,
    help="Set a date for this snapshot to be dropped.",
    required=False,
    default=None,
    callback=validate.callbacks.datetime_parsed,
    metavar=None,
    shell_complete=None,
)
@_pass.routine
@_pass.console
def create(
    console: "Console",
    routine: "CliQueryRoutines",
    name: str,
    expiration_timestamp: "datetime",
) -> None:
    """Create a snapshot."""
    routine._create_snapshot(name, expiration_timestamp, wait=True, render=True)
    console.print("Created snapshot", markup.code(name))


@click.command(
    cls=FormattedCommand,
    name="restore",
    short_help="Replace timesheet table with a snapshot.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not restore snapshot.")),
)
@_pass.routine
@_pass.console
@_pass.client
def restore(client: "Client", console: "Console", routine: "CliQueryRoutines") -> None:
    """Replace timesheet table with a snapshot."""
    try:
        snapshots = list(
            filter(
                lambda t: t.table_type == "SNAPSHOT",
                client.list_tables(routine.dataset),
            )
        )

        selection = _questionary.select(
            message="Which snapshot do you want to restore?",
            choices=list(map(_get.table_id, snapshots)),
            instruction="",
            use_indicator=True,
        )
    except ValueError as e:
        if str(e) == "A list of choices needs to be provided.":
            console.print(markup.dimmed("No snapshots exist"))
            raise click.exceptions.Exit
        else:
            console.print(markup.br(e))
            raise click.exceptions.Exit

    if _questionary.confirm(
        message="This will drop your timesheet table and replace it "
        "with a clone of this snapshot. Are you sure?",
        auto_enter=True,
        default=False,
    ):
        routine._restore_snapshot(selection, wait=True, render=True)
        console.print("Restored snapshot", markup.code(selection))

    else:
        console.print(markup.dimmed("Did not restore snapshot."))


@click.command(
    cls=FormattedCommand,
    name="list",
    short_help="List current snapshots.",
)
@_pass.routine
@_pass.console
def list_(console: "Console", routine: "CliQueryRoutines") -> None:
    """List current snapshots."""
    table: Table = render.map_sequence_to_rich_table(
        mappings=list(map(lambda r: dict(r.items()), routine._list_snapshots())),
        string_ctype=["table_name", "notes"],
        datetime_ctype=["creation_time", "snapshot_time_ms", "expiration_timestamp"],
    )
    if not table.row_count:
        rprint(markup.dimmed("No results"))
        raise click.exceptions.Exit
    console.print(table)


@click.command(
    cls=FormattedCommand,
    name="delete",
    short_help="Drop a snapshot.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dimmed("Did not delete snapshot.")),
)
@_pass.console
@_pass.client
def delete(client: "Client", console: "Console") -> None:
    """Drop a snapshot."""
    dataset = AppConfig().get("bigquery", "dataset")

    snapshots = list(
        filter(
            lambda t: t.table_type == "SNAPSHOT",
            client.list_tables(dataset),
        )
    )

    choices = list(map(_get.table_id, snapshots))

    if not choices:
        console.print(markup.dimmed("No snapshots exist"))
        raise click.exceptions.Exit

    selection = _questionary.checkbox(
        message="Select snapshots to delete $",
        choices=list(map(_get.table_id, snapshots)),
    )

    if selection and _questionary.confirm(
        message="Are you sure?", auto_enter=True, default=False
    ):
        for snapshot in selection:
            client.delete_table(f"{dataset}.{snapshot}")
            console.print("Deleted", markup.code(snapshot))
    else:
        console.print(markup.dimmed("Did not select any snapshots."))
