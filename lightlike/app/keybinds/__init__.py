
from typing import TYPE_CHECKING

from lightlike.app.keybinds.bindings import PROMPT_BINDINGS

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__: Sequence[str] = ("PROMPT_BINDINGS",)
