import secrets
from pathlib import Path

import jwt
from datetime import datetime, timedelta, timezone
from typing import Any


def load_or_create_secret(path: str | Path) -> str:
    """シークレットキーをファイルから読み込む。ファイルが存在しなければ生成して保存する。"""
    p = Path(path)
    if p.exists():
        return p.read_text().strip()
    secret = secrets.token_hex(32)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(secret)
    return secret


class TokenManager:
    def __init__(self, secret: str, algorithm: str = "HS256") -> None:
        self._secret = secret
        self._algorithm = algorithm

    @classmethod
    def from_file(
        cls, path: str | Path, algorithm: str = "HS256"
    ) -> "TokenManager":
        """ファイルからシークレットキーを読み込んでインスタンスを生成する。ファイルが存在しなければキーを自動生成する。"""
        secret = load_or_create_secret(path)
        return cls(secret, algorithm)

    def create_token(
        self,
        user_id: int,
        username: str,
        expires_delta: timedelta = timedelta(hours=1),
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "username": username,
            "iat": now,
            "exp": now + expires_delta,
        }
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def verify_token(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, self._secret, algorithms=[self._algorithm])
