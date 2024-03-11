import re
from typing import Sequence

import rich_click as click
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
)


class ExistingProject(Validator):
    def validate(self, document: "Document") -> None:
        if not document.text:
            raise ValidationError(
                cursor_position=0,
                message="Input cannot be none.",
            )
        elif not re.match(r"^[a-zA-Z0-9-\_]+$", document.text):
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
                message="Too short.",
            )
        elif len(document.text) > 20:
            raise ValidationError(
                cursor_position=0,
                message="Too long.",
            )
        elif not re.match(r"^[a-zA-Z0-9-\_]{3,20}$", document.text):
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


def active_project(ctx: click.Context, param: click.Parameter, value: str) -> str:
    if ctx.parent:
        if (
            ctx.parent.info_name == "project"
            and ctx.info_name in ("update", "delete", "archive", "unarchive")
            and value == "no-project"
        ):
            raise click.BadArgumentUsage(
                message="Cannot alter the default project.",
                ctx=ctx,
            )

    if value in projects.Active().names or value == "no-project":
        return value

    if value in projects.Archived().names:
        raise click.BadArgumentUsage(
            message="Project is archived. "
            "Unarchive before searching for this project.",
            ctx=ctx,
        )

    raise click.BadArgumentUsage(message="Project does not exist.", ctx=ctx)


def active_project_list(
    ctx: click.Context, param: click.Parameter, value: Sequence[str]
) -> Sequence[str]:
    if ctx.parent:
        if (
            ctx.parent.info_name == "project"
            and ctx.info_name in ("update", "delete")
            and "no-project" in value
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
    if value == "no-project":
        raise click.BadArgumentUsage(
            message="Cannot alter the default project.", ctx=ctx
        )
    elif ctx.parent and value in projects.Archived().names:
        return value
    else:
        raise click.BadArgumentUsage(message="Project does not exist.", ctx=ctx)
