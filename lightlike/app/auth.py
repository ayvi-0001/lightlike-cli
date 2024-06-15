# mypy: disable-error-code="func-returns-value"

from __future__ import annotations

import sys
import typing as t
from base64 import b64encode
from hashlib import sha3_256, sha256
from json import JSONDecodeError, loads
from os import urandom

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC, hashes
from prompt_toolkit import PromptSession
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.validation import Validator
from rich import get_console
from rich import print as rprint
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text

from lightlike.app.config import AppConfig
from lightlike.internal import markup, utils
from lightlike.internal.enums import CredentialsSource
from lightlike.lib.third_party import _questionary

if t.TYPE_CHECKING:
    from prompt_toolkit.key_binding import KeyPressEvent

__all__: t.Sequence[str] = ("_AuthSession",)


_Hash = type(sha256(b"_Hash"))


class _AuthSession:
    auth_keybinds: t.ClassVar[KeyBindings] = KeyBindings()
    hidden: t.ClassVar[list[bool]] = [True]

    @staticmethod
    @auth_keybinds.add(Keys.ControlT, eager=True)
    def _(event: "KeyPressEvent") -> None:
        _AuthSession.hidden[0] = not _AuthSession.hidden[0]

    @staticmethod
    @auth_keybinds.add(Keys.ControlQ, eager=True)
    def _(event: "KeyPressEvent") -> None:
        """Quit and reset all auth settings."""

        with AppConfig().rw() as config:
            config["user"].update(
                password="null",
                salt=[],
                stay_logged_in=False,
            )
            config["client"].update(
                active_project="null",
                credentials_source=CredentialsSource.not_set,
                service_account_key=[],
            )
        sys.exit(0)

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
        key_derivation = hashed.derive(password.encode())
        return b64encode(key_derivation)

    def authenticate(
        self,
        salt: bytes,
        encrypted_key: bytes,
        password: str | None = None,
        retry: bool = True,
    ) -> bytes:
        config_password = AppConfig().get("user", "password")
        saved_password = config_password if config_password != "null" else None
        stay_logged_in = AppConfig().get("user", "stay_logged_in")

        if saved_password and stay_logged_in:
            password = saved_password

        if not saved_password:
            if not password:
                password = self.prompt_password()

            password = sha256(password.encode()).hexdigest()  # type: ignore[union-attr]

        try:
            service_account_key = self.decrypt(
                self._generate_key(str(password), bytes(salt)),
                bytes(encrypted_key),
            )

        except InvalidToken:
            if saved_password:
                self._update_user_credentials(
                    password="null",
                    stay_logged_in=False,
                )
                rprint(
                    Panel(
                        Text.assemble(
                            markup.br("Saved credentials failed. "),
                            "Password input required.",
                        )
                    )
                )
            else:
                rprint(markup.br("Incorrect password."))

            if retry:
                return self.authenticate(salt, encrypted_key)

        except Exception as e:
            rprint(f"[bright_white on dark_red]{e}.")
            if saved_password:
                self._update_user_credentials(
                    password="null",
                    stay_logged_in=False,
                )
                rprint(
                    Panel(
                        Text.assemble(
                            markup.br("Saved credentials failed. "),
                            "Password input required.",
                        )
                    )
                )

            if retry:
                return self.authenticate(salt, encrypted_key)

        return self.load_bytes(service_account_key)

    def prompt_password(
        self, message: str = "(password) $ ", newline_breaks: bool = True
    ) -> str:
        newline_breaks and utils._nl()
        try:
            while 1:
                password = get_console().input(message, password=True)
                if password != "":
                    newline_breaks and utils._nl()
                    return password
        except (KeyboardInterrupt, EOFError):
            rprint(markup.br("\nAborted"))
            sys.exit(2)

    def prompt_new_password(self) -> tuple[sha3_256, bytes]:
        while 1:
            password = self.prompt_password()
            reenter_password = self.prompt_password(
                "(re-enter password) $ ", newline_breaks=False
            )
            if reenter_password == password:
                return sha256(password.encode()), urandom(32)
            else:
                rprint(markup.dimmed("Password does not match, please try again."))

    def prompt_service_account_key(self) -> str:
        panel = Panel.fit(
            Text.assemble(
                "Copy and paste service-account key. Press ",
                markup.code("esc enter"),
                " to continue.",
            )
        )
        rprint(Padding(panel, (1, 0, 1, 1)))

        session: PromptSession = PromptSession(
            message="(service-account-key) $ ",
            style=AppConfig().prompt_style,
            cursor=AppConfig().cursor_shape,
            multiline=True,
            refresh_interval=1,
            erase_when_done=True,
            key_bindings=self.auth_keybinds,
            is_password=Condition(lambda: self.hidden[0]),
            validator=Validator.from_callable(
                lambda d: False if not d else True,
                error_message="Input cannot be None.",
            ),
        )

        service_account_key = None

        try:
            while not service_account_key:
                key_input = session.prompt()
                try:
                    key = loads(key_input)
                except JSONDecodeError:
                    rprint(markup.br("Invalid json."))
                    continue
                else:
                    if (
                        "client_email" not in key.keys()
                        or "token_uri" not in key.keys()
                    ):
                        rprint(
                            Text.assemble(
                                "Invalid service-account json. Missing required key ",
                                markup.code("client_email"), " or ",
                                markup.code("token_uri"), ".\n",  # fmt: skip
                            )
                        )
                        continue
                    service_account_key = key_input
        except (KeyboardInterrupt, EOFError):
            rprint(markup.br("Aborted"))
            sys.exit(2)

        return service_account_key

    def _update_user_credentials(
        self,
        password: str | sha3_256 | list | None = None,
        salt: bytes | None = None,
        stay_logged_in: bool | None = None,
    ) -> None:
        with AppConfig().rw() as config:
            if password:
                if isinstance(password, str):
                    config["user"].update(
                        password=sha256(password.encode()).hexdigest(),
                    )

                elif isinstance(password, _Hash):
                    config["user"].update(
                        password=password.hexdigest(),
                    )

            if password == "null":
                config["user"].update(password="")
            if salt:
                config["user"].update(salt=salt)
            if stay_logged_in is not None:
                config["user"].update(stay_logged_in=stay_logged_in)

    @staticmethod
    def load_bytes(payload: bytes) -> bytes:
        return t.cast(bytes, loads(payload.decode()))

    def stay_logged_in(self, value: bool) -> None:
        from lightlike.app.client import service_account_key_flow

        if value is True:
            stay_logged_in = AppConfig().get("user", "stay_logged_in")

            if not stay_logged_in:
                rprint("Enter current password.")
                current = self.prompt_password()
                encrypted_key, salt = service_account_key_flow()

                try:
                    self.authenticate(
                        salt=salt,
                        encrypted_key=encrypted_key,
                        password=current,
                        retry=False,
                    )
                    self._update_user_credentials(
                        password=current, stay_logged_in=value
                    )
                    rprint("Set", markup.scope_key("stay_logged_in"), "to", value)
                except UnboundLocalError:
                    ...

            else:
                rprint(
                    markup.dimmed(f"`stay_logged_in` is already set to `{value}`,"),
                    markup.dimmed("nothing happened."),
                )

        elif value is False:
            if not AppConfig().get("user", "stay_logged_in"):
                rprint(markup.dimmed("Setting is already off."))

            else:
                self._update_user_credentials(password="null", stay_logged_in=False)
                rprint("Set", markup.scope_key("stay_logged_in"), "to", False)
