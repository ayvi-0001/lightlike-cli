import json
import sys
import typing as t
from base64 import b64encode
from hashlib import sha3_256, sha256
from os import urandom

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import (  # type: ignore[attr-defined] # fmt: skip
    PBKDF2HMAC,
    hashes,
)
from rich import get_console
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text

from lightlike.app.config import AppConfig
from lightlike.internal import markup, utils

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

    @staticmethod
    def load_json_bytes(payload: bytes) -> bytes:
        return t.cast(bytes, json.loads(payload.decode()))


class AuthPromptSession:
    def authenticate(
        self,
        salt: bytes,
        encrypted_key: bytes,
        password: str | None = None,
        retry: bool = True,
    ) -> bytes:
        auth = _Auth()

        config_password = AppConfig().get("user", "password")
        saved_password = config_password if config_password != "null" else None
        stay_logged_in = AppConfig().get("user", "stay_logged_in")

        if saved_password and stay_logged_in:
            password = saved_password

        if not saved_password:
            if not password:
                password = self.prompt_password()

            password = sha256(password.encode()).hexdigest()

        try:
            service_account_key = auth.decrypt(
                auth._generate_key(str(password), bytes(salt)),
                bytes(encrypted_key),
            )

        except Exception as error:
            if saved_password:
                AppConfig()._update_user_credentials(
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

            if type(error) == InvalidToken:
                if not saved_password:
                    rprint(markup.br("Incorrect password."))
            else:
                rprint(f"[bright_white on dark_red]{error!r} {error!s}.")

            if retry:
                return self.authenticate(salt, encrypted_key)

        return auth.load_json_bytes(service_account_key)

    def prompt_password(
        self, message: str = "(password) $ ", add_newline_breaks: bool = True
    ) -> str:
        add_newline_breaks and utils._nl()
        try:
            while 1:
                password = get_console().input(message, password=True)
                if password != "":
                    add_newline_breaks and utils._nl()
                    return password
        except (KeyboardInterrupt, EOFError):
            rprint(markup.br("\nAborted"))
            sys.exit(2)

    def prompt_new_password(self) -> tuple[sha3_256, bytes]:
        while 1:
            password = self.prompt_password()
            reenter_password = self.prompt_password(
                message="(re-enter password) $ ",
                add_newline_breaks=False,
            )
            if reenter_password == password:
                return sha256(password.encode()), urandom(32)
            else:
                rprint(markup.dimmed("Password does not match, please try again."))
