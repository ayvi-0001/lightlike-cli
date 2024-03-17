from typing import TYPE_CHECKING, Iterator, Sequence

from click.shell_completion import CompletionItem
from prompt_toolkit.completion import Completer, Completion

from lightlike.app.cache import TomlCache
from lightlike.internal.utils import _alter_str, _match_str

if TYPE_CHECKING:
    import rich_click as click
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

__all__: Sequence[str] = ("TimeCompleter", "date", "cached_timer_start")


def time(
    ctx: "click.Context", param: "click.Parameter", incomplete: str
) -> list[CompletionItem]:
    if not ctx.resilient_parsing:
        return []
    elif ctx.params.get("%s" % param.name) is None:
        return []
    elif not incomplete and not param.default:
        return []
    elif time_complete := _time_autocomplete(incomplete):
        return time_complete
    else:
        return []


def cached_timer_start(
    ctx: "click.Context", param: "click.Parameter", incomplete: str
) -> list[CompletionItem]:
    if cached_timer := TomlCache():
        start = cached_timer.start.time().replace(microsecond=0)

        if _match_str(incomplete, start, method="startswith"):
            value = _alter_str(start, add_quotes=True)
            return [CompletionItem(value=value, help="Current start time.")]

    return time(ctx, param, incomplete)


def _time_autocomplete(incomplete: str, quotes: bool = True) -> list[CompletionItem]:
    time_args = _get_time_args(incomplete)
    if time_args:
        # Not accounted for.
        if time_args[0][:1] in ("-", "+") or ("/" in incomplete or "\\" in incomplete):
            return []
        # Autocomplete time.
        elif ":" in incomplete:
            if time_complete := _complete_time(time_args, quotes):
                return time_complete
        # Autocomplete past time.
        elif any(list(map(lambda c: c.isnumeric(), incomplete))):
            if past_complete := _complete_past_qualifier(time_args, quotes):
                return past_complete

    return []


class TimeCompleter(Completer):
    def get_completions(
        self, document: "Document", complete_event: "CompleteEvent"
    ) -> Iterator[Completion]:
        if time_complete := _time_autocomplete(document.text, quotes=False):
            start_position = -len(document.text_before_cursor)
            completions = [
                Completion(
                    text=item.value,
                    start_position=start_position,
                    display=item.value,
                )
                for item in time_complete
            ]

            yield from completions


class TimeCompletion:
    def __init__(self, quotes: bool = True) -> None:
        self.quotes = quotes

    def past(self, num, q) -> list[CompletionItem]:
        value = "%d %s ago" % (num, q)
        value_q = _alter_str(value, add_quotes=True)
        return [CompletionItem(value=value_q if self.quotes else value)]

    def future(self, num, q) -> list[CompletionItem]:
        value = "in %d %s" % (num, q)
        value_q = _alter_str(value, add_quotes=True)
        return [CompletionItem(value=value_q if self.quotes else value)]


def _get_time_args(incomplete: str) -> list[str]:
    # Strip quotes from incomplete.
    incomplete_arr = _alter_str(incomplete, strip_quotes=True).split(" ")
    # Filter out whitespace.
    filtered_args = filter(lambda a: a != "", incomplete_arr)
    # Remove leading/trailing whitespace from passed args.
    return list(map(lambda a: a.strip(), filtered_args))


def _complete_time(time_args: list[str], quotes: bool = True) -> list[CompletionItem]:
    _time_parts = time_args[0].split(":")
    # Conditional for valid time start.
    if _time_parts and (hour := _time_parts[0]).isnumeric() and int(hour) <= 23:
        # Determine which time component is being typed.
        match len(_time_parts):
            case 2:  # Completing minute.
                if not _time_parts[-1]:
                    if len(hour) == 1:
                        typed_hour = f"0{hour}"
                    else:
                        typed_hour = _time_parts[0]

                    if len(typed_hour) <= 2 and typed_hour.isnumeric():
                        hour = typed_hour + ("0" * (2 - len(typed_hour)))
                        remaining = ":".join([hour, "00", "00"])
                        return [
                            CompletionItem(f"{remaining}" if quotes else remaining),
                        ]
                else:
                    typed_minute = _time_parts[1]

                    if len(typed_minute) <= 2 and typed_minute.isnumeric():
                        minute = typed_minute + ("0" * (2 - len(typed_minute)))
                        remaining = ":".join([hour, minute, "00"])
                        return [
                            CompletionItem(f"{remaining}" if quotes else remaining),
                        ]

            case 3:  # Completing second.
                if not _time_parts[-1]:
                    minute = _time_parts[1]
                    typed_second = _time_parts[2]

                    if all([2 >= len(c) > 0 for c in (minute, typed_second)]):
                        second = typed_second + ("0" * (2 - len(typed_second)))
                        remaining = ":".join([hour, minute, second])
                        return [
                            CompletionItem(f"{remaining}" if quotes else remaining),
                        ]
                else:
                    minute = _time_parts[1]
                    typed_second = _time_parts[2]

                    if all(
                        [len(c) <= 2 and c.isnumeric() for c in (minute, typed_second)],
                    ):
                        second = typed_second + ("0" * (2 - len(typed_second)))
                        remaining = ":".join([hour, minute, second])
                        return [
                            CompletionItem(f"{remaining}" if quotes else remaining),
                        ]
    return []


def _complete_past_qualifier(
    time_args: list[str], quotes: bool = True
) -> list[CompletionItem]:
    try:
        if n := int(time_args[0]):
            if len(time_args) > 1:
                typed_q = time_args[1]
                return _match_typed_qualifier(n, typed_q, quotes)
            else:
                return TimeCompletion(quotes).past(n, "min")
    except (ValueError, IndexError):
        pass
    return []


def _match_typed_qualifier(
    number: int, typed_qualifer: str, quotes: bool
) -> list[CompletionItem]:
    matches_typed = lambda s: s.startswith(typed_qualifer)
    if matches_typed(q := "min"):
        return TimeCompletion(quotes).past(number, q)
    elif matches_typed(q := "hours" if number ^ 1 else "hour"):
        return TimeCompletion(quotes).past(number, q)
    elif matches_typed(q := "days" if number ^ 1 else "day"):
        return TimeCompletion(quotes).past(number, q)
    elif matches_typed(q := "weeks" if number ^ 1 else "week"):
        return TimeCompletion(quotes).past(number, q)
    elif matches_typed(q := "months" if number ^ 1 else "month"):
        return TimeCompletion(quotes).past(number, q)
    elif matches_typed(q := "years" if number ^ 1 else "year"):
        return TimeCompletion(quotes).past(number, q)
    return []
