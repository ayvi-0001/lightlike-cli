import sys
import typing as t
from base64 import b64encode
from hashlib import sha3_256, sha256
from os import urandom
from secrets import compare_digest

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
from rich import get_console
from rich import print as rprint
from rich.console import NewLine

from lightlike.internal import constant

__all__: t.Sequence[str] = ("_Auth", "AuthPromptSession")


class _Auth:
    def encrypt(self, __key: bytes, __val: str) -> bytes:
        return Fernet(__key).encrypt(__val.encode())

    def decrypt(self, __key: bytes, encrypted: bytes) -> bytes:
        return Fernet(__key).decrypt(encrypted)

    def _generate_key(self, password: str, salt: bytes) -> bytes:
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
def _(event: KeyPressEvent) -> None:
    AUTH_KEY_HIDDEN[0] = not AUTH_KEY_HIDDEN[0]


class AuthPromptSession:
    def decrypt_key(
        self,
        salt: bytes,
        encrypted_key: bytes,
        saved_password: str | t.Callable[[], str | None] | None = None,
        stay_logged_in: bool | t.Callable[[], bool | None] | None = None,
        input_password: "sha3_256 | None" = None,
        retry: bool = True,
        saved_credentials_failed: t.Callable[[], None] | None = None,
    ) -> str:
        auth = _Auth()
        _saved_password: str | None = (
            saved_password() if callable(saved_password) else saved_password
        )
        _stay_logged_in: bool | None = (
            stay_logged_in() if callable(stay_logged_in) else stay_logged_in
        )

        password: str | None = None
        if _saved_password is not None and _stay_logged_in is True:
            password = _saved_password
        elif input_password:
            password = input_password.hexdigest()
        else:
            password = self.prompt_password().hexdigest()

        try:
            decrypted_key = auth.decrypt(
                auth._generate_key(password, bytes(salt)), bytes(encrypted_key)
            )
        except Exception as error:
            if _saved_password:
                if saved_credentials_failed is not None and callable(
                    saved_credentials_failed
                ):
                    saved_credentials_failed()
                rprint(
                    "[b][red]Saved credentials failed.",
                    "Password input required.",
                )
            elif type(error) == InvalidToken:
                if not _saved_password:
                    rprint("[b][red]Incorrect password.")
            else:
                rprint(f"[bright_white on dark_red]{error!r} {error!s}.")

            if retry:
                return self.decrypt_key(
                    salt,
                    encrypted_key,
                    saved_password,
                    stay_logged_in,
                    input_password,
                    retry,
                    saved_credentials_failed,
                )
            else:
                rprint("[b][red]Authentication failed.")
                sys.exit(2)

        return decrypted_key.decode()

    def prompt_password(
        self,
        prompt: str = "(password) $ ",
        add_newline_breaks: bool = True,
    ) -> sha3_256:
        add_newline_breaks and rprint(NewLine())
        try:
            while 1:
                password: sha3_256 = sha256(
                    get_console().input(prompt=prompt, password=True).encode()
                )
                add_newline_breaks and rprint(NewLine())
                return password
        except (KeyboardInterrupt, EOFError):
            rprint("\n[b][red]Aborted")
            sys.exit(1)

    def prompt_new_password(
        self,
        prompt: str = "(password) $ ",
        reprompt: str = "(re-enter password) $ ",
    ) -> tuple[sha3_256, bytes]:
        while 1:
            password: sha3_256 = self.prompt_password(prompt)
            reenter_password: sha3_256 = self.prompt_password(
                prompt=reprompt, add_newline_breaks=False
            )
            if compare_digest(password.digest(), reenter_password.digest()):
                return password, urandom(32)
            else:
                rprint("[#888888]Password does not match, try again.")

    def prompt_secret(self, message: str, add_newline_breaks: bool = True) -> str:
        add_newline_breaks and rprint(NewLine())
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
                lambda d: False if not d else True,
                error_message="Input cannot be None.",
            ),
        )
        retval: str = session.prompt()
        add_newline_breaks and rprint(NewLine())
        return retval
