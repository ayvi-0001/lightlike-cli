from __future__ import annotations

import typing as t

import rtoml
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.shortcuts import CompleteStyle, PromptSession
from prompt_toolkit.styles import BaseStyle, Style, StyleTransformation
from prompt_toolkit.validation import Validator
from typing_extensions import TypedDict

from lightlike.app import cursor, dates, shell_complete, validate
from lightlike.app.autosuggest import threaded_autosuggest
from lightlike.app.config import AppConfig
from lightlike.app.keybinds import PROMPT_BINDINGS
from lightlike.internal import appdir, constant, utils

if t.TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

__all__: t.Sequence[str] = ("PromptFactory",)


class PromptFactory[T](PromptSession[t.Any]):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # ty: ignore[invalid-argument-type]
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
        *,
        pre_run: bool = False,
        **prompt_kwargs: t.Unpack[PromptKwargs],  # ty: ignore[invalid-type-form]
    ) -> T:
        prompt: t.Any = cls().prompt(
            message=cursor.build(message),
            bottom_toolbar=cursor.bottom_toolbar,
            rprompt=cursor.rprompt,
            pre_run=utils.prerun_autocomplete if pre_run else None,
            **prompt_kwargs,  # ty: ignore[invalid-argument-type, parameter-already-assigned]
        )
        return prompt

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_date(
        cls,
        message: str,
        **prompt_kwargs: t.Unpack[PromptKwargs],
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
        **prompt_kwargs: t.Unpack[PromptKwargs],
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
        *,
        new: bool = False,
        **prompt_kwargs: t.Unpack[PromptKwargs],
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
        project: str = session.prompt(**session_pk)  # ty: ignore[invalid-argument-type]
        return project


if t.TYPE_CHECKING:
    from prompt_toolkit.auto_suggest import AutoSuggest
    from prompt_toolkit.clipboard import Clipboard
    from prompt_toolkit.completion import Completer
    from prompt_toolkit.cursor_shapes import AnyCursorShapeConfig
    from prompt_toolkit.document import Document
    from prompt_toolkit.enums import EditingMode
    from prompt_toolkit.eventloop import InputHook
    from prompt_toolkit.filters.base import FilterOrBool
    from prompt_toolkit.formatted_text import AnyFormattedText
    from prompt_toolkit.key_binding import KeyBindingsBase
    from prompt_toolkit.layout.processors import Processor
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.output import ColorDepth
    from prompt_toolkit.shortcuts.prompt import PromptContinuationText


class PromptKwargs(TypedDict):
    editing_mode: t.NotRequired[EditingMode | None]
    refresh_interval: t.NotRequired[float | None]
    vi_mode: t.NotRequired[bool | None]
    lexer: t.NotRequired[Lexer | None]
    completer: t.NotRequired[Completer | None]
    complete_in_thread: t.NotRequired[bool | None]
    is_password: t.NotRequired[bool | None]
    key_bindings: t.NotRequired[KeyBindingsBase | None]
    bottom_toolbar: t.NotRequired[AnyFormattedText | None]
    style: t.NotRequired[BaseStyle | None]
    color_depth: t.NotRequired[ColorDepth | None]
    cursor: t.NotRequired[AnyCursorShapeConfig | None]
    include_default_pygments_style: t.NotRequired[FilterOrBool | None]
    style_transformation: t.NotRequired[StyleTransformation | None]
    swap_light_and_dark_colors: t.NotRequired[FilterOrBool | None]
    rprompt: t.NotRequired[AnyFormattedText | None]
    multiline: t.NotRequired[FilterOrBool | None]
    prompt_continuation: t.NotRequired[PromptContinuationText | None]
    wrap_lines: t.NotRequired[FilterOrBool | None]
    enable_history_search: t.NotRequired[FilterOrBool | None]
    search_ignore_case: t.NotRequired[FilterOrBool | None]
    complete_while_typing: t.NotRequired[FilterOrBool | None]
    validate_while_typing: t.NotRequired[FilterOrBool | None]
    complete_style: t.NotRequired[CompleteStyle | None]
    auto_suggest: t.NotRequired[AutoSuggest | None]
    validator: t.NotRequired[Validator | None]
    clipboard: t.NotRequired[Clipboard | None]
    mouse_support: t.NotRequired[FilterOrBool | None]
    input_processors: t.NotRequired[list[Processor] | None]
    placeholder: t.NotRequired[AnyFormattedText | None]
    reserve_space_for_menu: t.NotRequired[int | None]
    enable_system_prompt: t.NotRequired[FilterOrBool | None]
    enable_suspend: t.NotRequired[FilterOrBool | None]
    enable_open_in_editor: t.NotRequired[FilterOrBool | None]
    tempfile_suffix: t.NotRequired[str | Callable[[], str] | None]
    tempfile: t.NotRequired[str | Callable[[], str] | None]
    show_frame: t.NotRequired[FilterOrBool | None]
    default: t.NotRequired[str | Document | None]
    accept_default: t.NotRequired[bool | None]
    pre_run: t.NotRequired[Callable[[], None] | None]
    set_exception_handler: t.NotRequired[bool | None]
    handle_sigint: t.NotRequired[bool | None]
    in_thread: t.NotRequired[bool | None]
    inputhook: t.NotRequired[InputHook | None]
