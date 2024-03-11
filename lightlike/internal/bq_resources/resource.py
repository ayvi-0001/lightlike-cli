import re
from typing import TYPE_CHECKING, Sequence

from prompt_toolkit.validation import ValidationError, Validator

if TYPE_CHECKING:
    from prompt_toolkit.document import Document

__all__: Sequence[str] = ("ResourceName",)


class ResourceName(Validator):
    def __init__(self) -> None:
        super().__init__()
        self.help_url = "https://cloud.google.com/bigquery/docs/datasets#dataset-naming"

    def validate(self, document: "Document") -> None:
        match = re.compile(r"^[a-zA-Z0-9_]*$").match(document.text)

        if not match:
            raise ValidationError(
                message=(
                    "Invalid name. Dataset names cannot contain spaces or special characters. "
                    f"{self.help_url}"
                ),
                cursor_position=0,
            )

        elif not document.text:
            raise ValidationError(
                message="Input cannot be empty.",
                cursor_position=0,
            )

        elif document.text.startswith("_"):
            raise ValidationError(
                message="Invalid name. Leading underscores are used for hidden resources.",
                cursor_position=0,
            )
