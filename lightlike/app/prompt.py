from __future__ import annotations

import typing as t

import rtoml
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import Validator

from lightlike.app import cursor, dates, shell_complete, validate
from lightlike.app.autosuggest import threaded_autosuggest
from lightlike.app.config import AppConfig
from lightlike.app.keybinds import PROMPT_BINDINGS
from lightlike.internal import appdir, constant, utils

if t.TYPE_CHECKING:
    from datetime import datetime

__all__: t.Sequence[str] = ("PromptFactory",)


T = t.TypeVar("T", bound="PromptFactory")


class PromptFactory(PromptSession[t.Any]):
    def __init__(self, **prompt_kwargs: t.Any) -> None:
        super().__init__(**prompt_kwargs)
        self.style = Style.from_dict(
            utils.update_dict(
                rtoml.load(constant.PROMPT_STYLE),
                AppConfig().get("prompt", "style", default={}),
            ),
        )
        self.history = appdir.REPL_FILE_HISTORY()
        self.cursor = CursorShape.BLOCK
        self.complete_in_thread = True
        self.validate_while_typing = True
        self.complete_while_typing = True
        self.enable_open_in_editor = True
        self.refresh_interval = 1
        self.key_bindings = PROMPT_BINDINGS

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def _prompt(
        cls,
        message: str,
        pre_run: bool = False,
        **prompt_kwargs: t.Any,
    ) -> t.Any:
        prompt: t.Any = cls().prompt(
            message=cursor.build(message),
            bottom_toolbar=cursor.bottom_toolbar,
            rprompt=cursor.rprompt,
            pre_run=utils.prerun_autocomplete if pre_run else None,
            **prompt_kwargs,
        )
        return prompt

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_date(
        cls,
        message: str,
        **prompt_kwargs: t.Any,
    ) -> datetime:
        from calendar import day_name, month_name

        session: t.Self = cls()
        suggestions: list[str] = ["yesterday", "today", "now"]
        suggestions.extend(month_name)
        suggestions.extend(day_name)

        session_pk: dict[str, t.Any] = {
            "message": cursor.build(message),
            "bottom_toolbar": cursor.bottom_toolbar,
            "rprompt": cursor.rprompt,
            "auto_suggest": threaded_autosuggest(suggestions),
            "validator": Validator.from_callable(
                bool,
                error_message="Input cannot be None.",
            ),
        }
        session_pk.update(**prompt_kwargs)
        date = session.prompt(**session_pk)
        return dates.parse_date(date, tzinfo=AppConfig().tzinfo)

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_note(
        cls,
        project: str,
        message: str = "(note)",
        **prompt_kwargs: t.Any,
    ) -> str:
        session: t.Self = cls()
        session_pk: dict[str, t.Any] = {
            "message": cursor.build(message),
            "bottom_toolbar": cursor.bottom_toolbar,
            "rprompt": cursor.rprompt,
            "pre_run": utils.prerun_autocomplete,
            "completer": shell_complete.notes.Notes(project),
            "validator": Validator.from_callable(
                bool,
                error_message="Input cannot be None.",
            ),
        }
        session_pk.update(**prompt_kwargs)
        note: str = session.prompt(**session_pk)
        return note

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_project(
        cls,
        message: str = "(project)",
        new: bool = False,
        **prompt_kwargs: t.Any,
    ) -> str:
        session: t.Self = cls()
        session_pk = {
            "message": cursor.build(message),
            "bottom_toolbar": cursor.bottom_toolbar,
            "rprompt": cursor.rprompt,
            "pre_run": utils.prerun_autocomplete,
            "completer": shell_complete.projects.Active() if not new else None,
            "validator": validate.ExistingProject() if not new else validate.NewProject(),
        }
        session_pk.update(**prompt_kwargs)
        project: str = session.prompt(**session_pk)
        return project
