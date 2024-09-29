import typing as t

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

from lightlike.app.config import AppConfig
from lightlike.app.keybinds import factory
from lightlike.internal.enums import ActiveCompleter

__all__: t.Sequence[str] = ("PROMPT_BINDINGS",)


PROMPT_BINDINGS = KeyBindings()

KEYBINDINGS = AppConfig().get("keys", default={})
COMPLETERS = KEYBINDINGS.get("completers", {})

# fmt: off
factory.add_exit_kb(PROMPT_BINDINGS, KEYBINDINGS.get("exit", [[]]))
factory.add_system_cmd_kb(PROMPT_BINDINGS, KEYBINDINGS.get("system-command", [[]]))
factory.add_global_completer_kb(PROMPT_BINDINGS, COMPLETERS.get("commands", [[]]), ActiveCompleter.CMD)
factory.add_global_completer_kb(PROMPT_BINDINGS, COMPLETERS.get("history", [[]]), ActiveCompleter.HISTORY)
factory.add_global_completer_kb(PROMPT_BINDINGS, COMPLETERS.get("path", [[]]), ActiveCompleter.PATH)
factory.add_global_completer_kb(PROMPT_BINDINGS, COMPLETERS.get("exec", [[]]), ActiveCompleter.EXEC)

del KEYBINDINGS, COMPLETERS

PROMPT_BINDINGS.add(Keys.Escape, eager=True, filter=factory.is_complete_state)(factory.autocomplete_apply)
PROMPT_BINDINGS.add(Keys.ControlSpace)(factory.autocomplete_next)
