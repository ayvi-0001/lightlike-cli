import re
from typing import Sequence

import click
from prompt_toolkit.document import Document
from prompt_toolkit.validation import ValidationError, Validator

from lightlike.app.shell_complete import projects

__all__: Sequence[str] = (
    "ExistingProject",
    "NewProject",
    "active_project",
    "active_project_list",
    "new_project",
    "archived_project",
    "archived_project_list",
)


DEFAULT_PROJECT: str = "no-project"


class ExistingProject(Validator):
    def validate(self, document: "Document") -> None:
        if not document.text:
            raise ValidationError(
                cursor_position=0,
                message="Input cannot be none.",
            )
        elif not re.match(r"^[a-zA-Z0-9-\_\.]{3,30}$", document.text):
            raise ValidationError(
                cursor_position=0,
                message="Invalid project name.",
            )
        elif document.text in projects.Archived().names:
            raise ValidationError(
                cursor_position=0,
                message="Project is archived. Unarchive before searching for this project.",
            )
        elif document.text not in projects.Active().names:
            raise ValidationError(
                cursor_position=0,
                message="Project does not exist.",
            )


class NewProject(Validator):
    def callback(self, name: str) -> None:
        return self.validate(Document(text=name))

    def validate(self, document: "Document") -> None:
        if not document.text:
            raise ValidationError(
                cursor_position=0,
                message="Cannot be none.",
            )
        elif document.text == "no-project":
            raise ValidationError(
                cursor_position=0,
                message="Reserved for default project.",
            )
        elif len(document.text) < 3:
            raise ValidationError(
                cursor_position=0,
                message="Name too short.",
            )
        elif len(document.text) > 25:
            raise ValidationError(
                cursor_position=0,
                message="Name too long.",
            )
        elif not re.match(r"^[a-zA-Z0-9-\_\.]{3,30}$", document.text):
            raise ValidationError(
                cursor_position=0,
                message="Invalid characters.",
            )
        elif document.text in projects.Archived().names:
            raise ValidationError(
                cursor_position=0,
                message="Project already exists in archive.",
            )
        elif document.text in projects.Active().names:
            raise ValidationError(
                cursor_position=0,
                message="Project already exists.",
            )


def active_project(
    ctx: click.Context, param: click.Parameter, value: str
) -> str | None:
    if ctx.info_name and ctx.parent and ctx.parent.info_name:
        group: str = ctx.parent.info_name
        cmd: str = ctx.info_name
        if (
            group == "project"
            and cmd in ("update", "delete", "archive", "unarchive")
            and value == DEFAULT_PROJECT
        ):
            raise click.BadArgumentUsage(
                message="Cannot alter the default project.",
                ctx=ctx,
            )
        elif group == "timer" and cmd == "edit" and not value:
            return None
    if value in projects.Archived().names:
        raise click.BadArgumentUsage(
            message="Project is archived. "
            "Unarchive before searching for this project.",
            ctx=ctx,
        )
    if value in projects.Active().names or value == DEFAULT_PROJECT:
        return value

    raise click.BadArgumentUsage(
        message="Project does not exist.",
        ctx=ctx,
    )


def active_project_list(
    ctx: click.Context, param: click.Parameter, value: Sequence[str]
) -> Sequence[str]:
    if ctx.parent:
        if (
            ctx.parent.info_name == "project"
            and ctx.info_name in ("update", "delete")
            and DEFAULT_PROJECT in value
        ):
            raise click.BadArgumentUsage(
                message="Cannot delete/update default project.",
                ctx=ctx,
            )

    if any([name in projects.Archived().names for name in value]):
        raise click.BadArgumentUsage(
            message="One or more selected projects is archived. "
            "Unarchive before searching for this project.",
            ctx=ctx,
        )

    if all([name in projects.Active().names for name in value]):
        return value

    raise click.BadArgumentUsage(
        message="One or more selected projects does not exist.",
        ctx=ctx,
    )


def new_project(ctx: click.Context, param: click.Parameter, value: str) -> str:
    if value:
        try:
            NewProject().callback(value)
            return value
        except ValidationError as e:
            raise click.ClickException(message=f"{e}")

    return value


def archived_project(ctx: click.Context, param: click.Parameter, value: str) -> str:
    if value == DEFAULT_PROJECT:
        raise click.BadArgumentUsage(
            message="Cannot alter the default project.", ctx=ctx
        )
    elif ctx.parent and value in projects.Archived().names:
        return value
    else:
        raise click.BadArgumentUsage(
            message="Project does not exist.",
            ctx=ctx,
        )


def archived_project_list(
    ctx: click.Context, param: click.Parameter, value: Sequence[str]
) -> Sequence[str]:
    if all([name in projects.Archived().names for name in value]):
        return value

    raise click.BadArgumentUsage(
        message="One or more selected projects does not exist.",
        ctx=ctx,
    )
