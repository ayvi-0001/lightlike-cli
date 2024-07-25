import typing as t
from dataclasses import dataclass
from pathlib import Path
from threading import Thread

from google.api_core.exceptions import BadRequest
from google.cloud.bigquery import Client
from more_itertools import zip_equal
from rich import get_console
from rich import print as rprint
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import Progress, TaskID

from lightlike.app import _questionary
from lightlike.internal import markup
from lightlike.internal.utils import _regexp_replace

__all__: t.Sequence[str] = ("run", "SCRIPTS")


SCRIPTS: t.Final[Path] = Path(__file__).parent.joinpath("sql").resolve()


@dataclass
class Build:
    name: str
    ordinal: int

    @property
    def path(self) -> Path:
        return SCRIPTS / self.name

    @property
    def scripts(self) -> t.Sequence[Path]:
        return tuple(
            filter(
                lambda p: p.suffix == ".sql" and not p.name.startswith("_"),
                self.path.iterdir(),
            )
        )

    @property
    def names(self) -> t.Sequence[str]:
        return tuple((path.name for path in self.scripts))


BUILDS: list[Build] = []

for idx, _path in enumerate(SCRIPTS.iterdir()):
    if _path.is_dir():
        BUILDS.append(Build(_path.name, ordinal=idx + 1))


def _run_script(
    client: "Client",
    path: Path,
    patterns: dict[str, str],
    step_progress: Progress,
    task_id: TaskID,
) -> None:
    try:
        step_progress.update(task_id, advance=1)
        script = _regexp_replace(patterns=patterns, text=path.read_text())
        step_progress.update(task_id, advance=1)
        script = script.replace("${__name__}", path.stem)
        step_progress.update(task_id, advance=1)
        client.query(script).result()
        step_progress.update(task_id, advance=1)
    except BadRequest as error:
        rprint(markup.br("Error in script:"), markup.repr_url(path.name))
        rprint(markup.red(error))


def _run_build_scripts(
    client: "Client",
    build: Build,
    patterns: dict[str, str],
    app_steps_task_id: TaskID,
    step_progress: Progress,
    build_steps_progress: Progress,
) -> None:
    threads: list[Thread] = []
    task_ids: list[TaskID] = []

    for idx, path in enumerate(build.scripts):
        task_id = step_progress.add_task(
            "", action=build.names[idx], name=build.name, total=6, start=False
        )

        thread = Thread(
            target=_run_script,
            name=f"Thread-N{task_id}",
            args=(client, path, patterns, step_progress, task_id),
            daemon=True,
        )
        threads.append(thread)
        task_ids.append(task_id)

    for thread, task_id in zip_equal(threads, task_ids):
        step_progress.start_task(task_id)
        thread.start()

    for thread in threads:
        thread.join()
        task_id = TaskID(int(thread.name.removeprefix("Thread-N")))
        step_progress.update(task_id, advance=1, visible=False)
        build_steps_progress.update(app_steps_task_id, advance=1)


def run(client: "Client", patterns: dict[str, str]) -> bool:
    from rich.live import Live
    from rich.progress import BarColumn, SpinnerColumn, TextColumn, TimeElapsedColumn

    overall_progress = Progress(
        TimeElapsedColumn(),
        BarColumn(),
        TextColumn("{task.description}"),
        refresh_per_second=30,
    )

    current_build_progress = Progress(
        TimeElapsedColumn(),
        TextColumn("{task.description}"),
        refresh_per_second=30,
    )

    step_progress = Progress(
        TextColumn("  "),
        TimeElapsedColumn(),
        TextColumn("[b][purple]{task.fields[action]}"),
        SpinnerColumn("simpleDotsScrolling"),
        refresh_per_second=30,
    )

    build_steps_progress = Progress(
        TextColumn(
            "[#32ccfe]Progress for build: "
            "{task.fields[name]}: {task.percentage:.0f}%"
        ),
        BarColumn(),
        TextColumn("[b][#f0f0ff]({task.completed} of {task.total} scripts done)"),
        refresh_per_second=30,
    )

    progress_group = Group(
        Padding(
            Panel.fit(
                Group(
                    current_build_progress,
                    step_progress,
                    build_steps_progress,
                )
            ),
            (1, 1, 1, 1),
        ),
        Padding(overall_progress, (1, 0, 0, 0)),
    )

    overall_task_id = overall_progress.add_task("", total=len(BUILDS))

    with get_console().screen(style="bold white on red"):
        with Live(progress_group, transient=True):
            for idx, build in enumerate(BUILDS):
                description_overall_progress = (
                    "[b][#f0f0ff](%d out of %d builds completed)" % (idx, len(BUILDS))
                )

                overall_progress.update(
                    overall_task_id, description=description_overall_progress
                )

                current_task_id = current_build_progress.add_task(
                    "[#f0f0ff]Running scripts for %s" % build.name
                )

                build_steps_task_id = build_steps_progress.add_task(
                    "", total=len(range(len(build.scripts))), name=build.name
                )

                _run_build_scripts(
                    client,
                    build,
                    patterns,
                    build_steps_task_id,
                    step_progress,
                    build_steps_progress,
                )

                build_steps_progress.update(
                    build_steps_task_id, advance=1, visible=False
                )
                current_build_progress.stop_task(current_task_id)

                current_build_progress.update(
                    current_task_id,
                    description="[b][green]%s completed." % build.name,
                )

                overall_progress.update(overall_task_id, advance=1)

            overall_progress.update(
                overall_task_id,
                description="[b][green]%d/%d builds completed."
                % (len(BUILDS), len(BUILDS)),
            )

        _questionary.press_any_key_to_continue(
            message="Build complete. Press any key to return to console."
        )

    return True
