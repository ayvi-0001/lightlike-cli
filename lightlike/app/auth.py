from __future__ import annotations

from base64 import b64encode
from hashlib import sha3_256, sha256
from json import JSONDecodeError, loads
from os import urandom
from typing import TYPE_CHECKING, ClassVar, Sequence, cast

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC, hashes
from prompt_toolkit import PromptSession
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.validation import Validator
from rich import get_console
from rich.padding import Padding
from rich.panel import Panel

from lightlike.app.config import AppConfig
from lightlike.internal import utils
from lightlike.internal.enums import CredentialsSource
from lightlike.lib.third_party import _questionary

if TYPE_CHECKING:
    from prompt_toolkit.key_binding import KeyPressEvent
    from rich.console import Console

__all__: Sequence[str] = ("_AuthSession",)


_Hash = type(sha256(b"_Hash"))


class _AuthSession:
    auth_keybinds: ClassVar[KeyBindings] = KeyBindings()
    hidden: ClassVar[list[bool]] = [True]
    console: ClassVar["Console"] = get_console()

    @staticmethod
    @auth_keybinds.add(Keys.ControlT, eager=True)
    def _(event: "KeyPressEvent") -> None:
        _AuthSession.hidden[0] = not _AuthSession.hidden[0]

    @staticmethod
    @auth_keybinds.add(Keys.ControlQ, eager=True)
    def _(event: "KeyPressEvent") -> None:
        """Quit and reset all auth settings."""

        with AppConfig().update() as config:
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
        exit(0)

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
        encrypted_key: bytearray,
        password: str | None = None,
        retry: bool = True,
    ) -> bytes:
        saved_settings = AppConfig().get("user", "password")
        saved_password = None if saved_settings == "null" else saved_settings
        saved_password = saved_settings if saved_settings != "null" else None

        stay_logged_in = AppConfig().get("user", "stay_logged_in")

        if saved_password and stay_logged_in:
            password = saved_password

        if not saved_password:
            if not password:
                try:
                    password = self.prompt_password()
                except (KeyboardInterrupt, EOFError):
                    exit(1)

            password = sha256(password.encode()).hexdigest()

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
                self.console.print(
                    Panel(
                        "[b][i][red]Saved credentials failed. "
                        "Password input required[/b][/i][/red].\n"
                        "Enter password."
                    )
                )
            else:
                self.console.print("[b][red]Incorrect password.")

            if retry:
                return self.authenticate(salt, encrypted_key)

        except Exception as e:
            self.console.print(f"[bright_white on dark_red]{e}.\n")
            if saved_password:
                self._update_user_credentials(
                    password="null",
                    stay_logged_in=False,
                )
                self.console.print(
                    Panel(
                        "[b][i][red]Saved credentials failed. "
                        "Password input required[/b][/i][/red].\n"
                        "Enter password."
                    )
                )

            if retry:
                return self.authenticate(salt, encrypted_key)

        return self.load_bytes(service_account_key)

    def prompt_password(self) -> str:
        # session: PromptSession = PromptSession(
        #     message="(password) $ ",
        #     style=AppConfig().prompt_style,
        #     cursor=AppConfig().cursor_shape,
        #     key_bindings=self.auth_keybinds,
        #     is_password=Condition(lambda: self.hidden[0]),
        #     rprompt="Press ctrl+t to toggle password visibility.",
        #     validator=Validator.from_callable(
        #         lambda d: False if not d else True,
        #         error_message="Input cannot be None.",
        #     ),
        #     erase_when_done=True,
        # )
        # return session.prompt()
        password = self.console.input("(password) $ ", password=True)
        return password

    def prompt_new_password(self) -> tuple[sha3_256, bytes]:
        password = None

        while not password:
            user_input = sha256(self.prompt_password().encode())

            utils._nl()
            if _questionary.confirm(message="Continue with this password?"):
                password = user_input
                utils._nl()

        salt = urandom(32)
        return password, salt

    def prompt_service_account_key(self) -> str:
        self.console.print(
            Padding(
                Panel.fit(
                    "Copy and paste service-account key. Press "
                    "[code]esc[/code] + [code]enter[/code] to continue."
                ),
                (1, 0, 1, 1),
            )
        )

        session: PromptSession = PromptSession(
            message="(service-account-key) $ ",
            style=AppConfig().prompt_style,
            cursor=AppConfig().cursor_shape,
            refresh_interval=1,
            multiline=True,
            is_password=Condition(lambda: self.hidden[0]),
            validator=Validator.from_callable(
                lambda d: False if not d else True,
                error_message="Input cannot be None.",
            ),
            erase_when_done=True,
        )
        service_account_key = None

        while not service_account_key:
            key_input = session.prompt()
            try:
                key = loads(key_input)
            except JSONDecodeError:
                self.console.print("[b][red]Invalid json.\n")
                continue
            else:
                if "client_email" not in key.keys() or "token_uri" not in key.keys():
                    self.console.print(
                        "Invalid service-account json. Missing required key "
                        "[code]client_email[/code] or [code]token_uri[/code].\n"
                    )
                    continue
                service_account_key = key_input

        return service_account_key

    def _update_user_credentials(
        self,
        password: str | sha3_256 | list | None = None,
        salt: bytes | None = None,
        stay_logged_in: bool | None = None,
    ) -> None:
        with AppConfig().update() as config:
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
        return cast(bytes, loads(payload.decode()))

    def stay_logged_in(self, value: bool) -> None:
        from lightlike.app.client import service_account_key_flow

        if value is True:
            stay_logged_in = AppConfig().get("user", "stay_logged_in")

            if not stay_logged_in:
                self.console.print("\nEnter current password.\n")
                current = self.console.input("(password) $ ", password=True)

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
                    utils.print_updated_val(key="stay_logged_in", val=value)
                except UnboundLocalError:
                    ...

            else:
                self.console.print("[d]Setting is already on.")

        elif value is False:
            if not AppConfig().get("user", "stay_logged_in"):
                self.console.print("[d]Setting is already off.")

            else:
                self._update_user_credentials(password="null", stay_logged_in=False)
                utils.print_updated_val(key="stay_logged_in", val=False)
