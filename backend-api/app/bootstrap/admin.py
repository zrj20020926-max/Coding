from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.services.admin_accounts import (
    AdminAccountError,
    AdminCreateInput,
    create_admin,
    promote_admin,
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="CodeArena administrator bootstrap")
    subcommands = command.add_subparsers(dest="command", required=True)
    create = subcommands.add_parser("create", help="create an administrator")
    create.add_argument("--username")
    create.add_argument("--email")
    create.add_argument("--nickname")
    create.add_argument("--password")
    create.add_argument("--secret-file", type=Path)
    promote = subcommands.add_parser("promote", help="promote an existing user")
    promote.add_argument("--username")
    promote.add_argument("--secret-file", type=Path)
    return command


def _read_secret_file(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        raw = path.read_text(encoding="utf-8-sig")
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdminAccountError("Secret 文件必须是可读取的 UTF-8 JSON 对象") from exc
    if not isinstance(value, dict):
        raise AdminAccountError("Secret 文件根节点必须是 JSON 对象")
    allowed = {"username", "email", "nickname", "password"}
    if set(value) - allowed:
        raise AdminAccountError("Secret 文件包含未知字段")
    return value


def _value(args: argparse.Namespace, secret: dict[str, Any], name: str) -> str:
    current = getattr(args, name, None)
    if current is not None:
        return str(current)
    if name in secret:
        return str(secret[name])
    if name == "password":
        return getpass.getpass("Password: ")
    return input(f"{name}: ").strip()


async def execute(args: argparse.Namespace) -> dict[str, Any]:
    secret = _read_secret_file(args.secret_file)
    try:
        async with SessionLocal() as db:
            if args.command == "create":
                payload = AdminCreateInput(
                    username=_value(args, secret, "username"),
                    email=_value(args, secret, "email"),
                    nickname=_value(args, secret, "nickname"),
                    password=_value(args, secret, "password"),
                )
                result = await create_admin(
                    db, payload, production=settings.app_env.casefold() == "production"
                )
            else:
                result = await promote_admin(db, _value(args, secret, "username"))
    finally:
        await engine.dispose()
    return {
        "status": "success",
        "action": result.action,
        "changed": result.changed,
        "user_id": str(result.user_id),
        "username": result.username,
    }


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = asyncio.run(execute(args))
    except AdminAccountError as exc:
        print(
            json.dumps(
                {"status": "error", "code": "ADMIN_BOOTSTRAP_FAILED", "message": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    except ValidationError:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": "ADMIN_INPUT_INVALID",
                    "message": "管理员账号参数校验失败",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
