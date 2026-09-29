import sys
import typing as t
from base64 import b64encode
from hashlib import sha256
from os import urandom
from secrets import compare_digest

import rich
import rtoml
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from prompt_toolkit import PromptSession
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import Validator
from rich.console import NewLine

from lightlike.internal import constant

if t.TYPE_CHECKING:
    from hashlib import _Hash


__all__: t.Sequence[str] = ("AuthPromptSession", "_Auth")


class _Auth:
    @staticmethod
    def encrypt(__key: bytes, __val: str, /) -> bytes:
        return Fernet(__key).encrypt(__val.encode())

    @staticmethod
    def decrypt(__key: bytes, encrypted: bytes, /) -> bytes:
        return Fernet(__key).decrypt(encrypted)

    @staticmethod
    def generate_key(password: str, salt: bytes) -> bytes:
        hashed = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            iterations=100000,
            length=32,
            salt=salt,
        )
        key_derivation: bytes = hashed.derive(password.encode())
        return b64encode(key_derivation)


AUTH_BINDINGS: KeyBindings = KeyBindings()
AUTH_KEY_HIDDEN: list[bool] = [True]


@AUTH_BINDINGS.add(Keys.ControlT, eager=True)
def _(_event: KeyPressEvent) -> None:
    AUTH_KEY_HIDDEN[0] = not AUTH_KEY_HIDDEN[0]


class AuthPromptSession:
    def decrypt_key(
        self,
        salt: bytes,
        encrypted_key: bytes,
        saved_password: str | t.Callable[[], str | None] | None = None,
        input_password: _Hash | None = None,
        saved_credentials_failed: t.Callable[[], None] | None = None,
        *,
        stay_logged_in: bool | t.Callable[[], bool | None] | None = None,
        retry: bool = True,
    ) -> str:
        auth = _Auth()
        saved_password_: str | None = (
            saved_password() if callable(saved_password) else saved_password
        )
        stay_logged_in_: bool | None = (
            stay_logged_in() if callable(stay_logged_in) else stay_logged_in
        )

        if saved_password_ is not None and stay_logged_in_ is True:
            password = saved_password_
        elif input_password:
            password = input_password.hexdigest()
        else:
            password = self.prompt_password().hexdigest()

        try:
            decrypted_key = auth.decrypt(
                auth.generate_key(password, bytes(salt)),
                bytes(encrypted_key),
            )
        except Exception as exc:  # ruff: ignore[blind-except]
            if saved_password_:
                if saved_credentials_failed is not None and callable(
                    saved_credentials_failed,
                ):
                    saved_credentials_failed()
                rich.print(
                    "[b][red]Saved credentials failed.",
                    "Password input required.",
                )
            elif isinstance(exc, InvalidToken):
                if not saved_password_:
                    rich.print("[b][red]Incorrect password.")
            else:
                rich.print(f"[bright_white on dark_red]{exc!r} {exc!s}.")

            if retry:
                return self.decrypt_key(
                    salt,
                    encrypted_key,
                    saved_password,
                    input_password,
                    saved_credentials_failed,
                    stay_logged_in=stay_logged_in,
                    retry=retry,
                )

            rich.print("[b][red]Authentication failed.")
            sys.exit(2)

        return decrypted_key.decode()

    @staticmethod
    def prompt_password(
        prompt: str = "(password) $ ",
        *,
        add_newline_breaks: bool = True,
    ) -> _Hash:
        add_newline_breaks and rich.print(NewLine())
        try:
            while True:
                data: bytes = rich.get_console().input(prompt=prompt, password=True).encode()
                password: _Hash = sha256(data)
                add_newline_breaks and rich.print(NewLine())
                return password
        except KeyboardInterrupt, EOFError:
            rich.print("\n[b][red]Aborted")
            sys.exit(1)

    def prompt_new_password(
        self,
        prompt: str = "(password) $ ",
        reprompt: str = "(re-enter password) $ ",
    ) -> tuple[_Hash, bytes]:
        while True:
            password: _Hash = self.prompt_password(prompt)
            reenter_password: _Hash = self.prompt_password(
                prompt=reprompt,
                add_newline_breaks=False,
            )
            if compare_digest(password.digest(), reenter_password.digest()):
                return password, urandom(32)
            rich.print("[#888888]Password does not match, try again.")

    @staticmethod
    def prompt_secret(message: str, *, add_newline_breaks: bool = True) -> str:
        add_newline_breaks and rich.print(NewLine())
        session: PromptSession[str] = PromptSession(
            message=message,
            style=Style.from_dict(rtoml.load(constant.PROMPT_STYLE)),
            cursor=CursorShape.BLOCK,
            multiline=True,
            refresh_interval=1,
            erase_when_done=True,
            key_bindings=AUTH_BINDINGS,
            is_password=Condition(lambda: AUTH_KEY_HIDDEN[0]),
            validator=Validator.from_callable(
                bool,
                error_message="Input cannot be None.",
            ),
        )
        retval: str = session.prompt()
        add_newline_breaks and rich.print(NewLine())
        return retval
