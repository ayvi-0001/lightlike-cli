# mypy: disable-error-code="arg-type"
from __future__ import annotations

from calendar import day_name, month_name
from typing import TYPE_CHECKING, Any, Sequence, cast

import rich_click as click
from dateparser import parse
from prompt_toolkit.shortcuts import CompleteStyle, PromptSession
from prompt_toolkit.validation import Validator
from rich.text import Text

from lightlike.app import cursor, shell_complete, validate
from lightlike.app.autosuggest import _threaded_autosuggest
from lightlike.app.config import AppConfig
from lightlike.app.key_bindings import PROMPT_BINDINGS
from lightlike.internal import markup, utils

if TYPE_CHECKING:
    from datetime import datetime

    from dateparser import _Settings

__all__: Sequence[str] = ("PromptFactory", "REPL_PROMPT_KWARGS")


REPL_PROMPT_KWARGS = dict(
    message=cursor.build,
    history=AppConfig().history,
    style=AppConfig().prompt_style,
    cursor=AppConfig().cursor_shape,
    key_bindings=PROMPT_BINDINGS,
    refresh_interval=1,
    complete_in_thread=True,
    complete_while_typing=True,
    validate_while_typing=True,
    enable_system_prompt=True,
    reserve_space_for_menu=AppConfig().get(
        "settings",
        "reserve_space_for_menu",
        default=7,
    ),
    complete_style=cast(
        CompleteStyle,
        AppConfig().get(
            "settings",
            "complete_style",
            default="COLUMN",
        ),
    ),
)


class PromptFactory(PromptSession):
    def __init__(self, **prompt_kwargs) -> None:
        super().__init__(**prompt_kwargs)
        self.style = AppConfig().prompt_style
        self.history = AppConfig().history
        self.cursor = AppConfig().cursor_shape
        self.complete_in_thread = True
        self.validate_while_typing = True
        self.complete_while_typing = True
        self.refresh_interval = 1
        self.key_bindings = PROMPT_BINDINGS

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def _prompt(cls, message: str, pre_run: bool = False, **prompt_kwargs) -> Any:
        prompt = cls().prompt(
            message=cursor.build(message),
            pre_run=utils._prerun_autocomplete if pre_run else None,
            **prompt_kwargs,
        )
        return prompt

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_for_date(cls, message: str, **prompt_kwargs) -> "datetime":
        session = cls()

        suggestions = ["yesterday", "today", "now"]
        suggestions.extend(month_name)
        suggestions.extend(day_name)

        session_pk = dict(
            message=cursor.build(message),
            completer=shell_complete.TimeCompleter(),
            auto_suggest=_threaded_autosuggest(suggestions),
            validator=Validator.from_callable(
                lambda d: False if not d else True,
                error_message="Input cannot be None.",
            ),
        )
        session_pk.update(**prompt_kwargs)
        date = session.prompt(**session_pk)
        parsed_date = session._parse_date(date)
        return parsed_date

    @staticmethod
    def _parse_date(date: str) -> "datetime":
        parser_settings = cast(
            "_Settings",
            {
                "RELATIVE_BASE": AppConfig().now,
                "PREFER_DATES_FROM": "past",
            },
        )
        parsed_date = parse(date, settings=parser_settings)
        if not parsed_date:
            raise click.UsageError(
                message=Text.assemble(
                    f"Failed to parse date: ", markup.code(date)
                ).markup,
                ctx=click.get_current_context(),
            )
        return AppConfig().in_app_timezone(parsed_date.replace(microsecond=0))

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_note(cls, project: str, message: str = "(note)", **prompt_kwargs) -> str:
        session = cls()

        session_pk = dict(
            message=cursor.build(message, hide_rprompt=True),
            pre_run=utils._prerun_autocomplete,
            completer=shell_complete.notes.Notes(project),
            rprompt=f"Project: {project}",
            validator=Validator.from_callable(
                lambda d: False if not d else True,
                error_message="Input cannot be None.",
            ),
        )
        session_pk.update(**prompt_kwargs)
        note = session.prompt(**session_pk)
        return note

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_project(
        cls, message: str = "(project)", new: bool = False, **prompt_kwargs
    ) -> str:
        session = cls()

        validator = validate.ExistingProject() if not new else validate.NewProject()
        completer = shell_complete.projects.Active() if not new else None
        bottom_toolbar = lambda: (
            "Name must match regex ^[a-zA-Z0-9-\_]{3,20}$" if new else None
        )

        session_pk = dict(
            message=cursor.build(message, hide_rprompt=True),
            pre_run=utils._prerun_autocomplete,
            completer=completer,
            validator=validator,
            bottom_toolbar=bottom_toolbar,
        )
        session_pk.update(**prompt_kwargs)
        project = session.prompt(**session_pk)
        return project
