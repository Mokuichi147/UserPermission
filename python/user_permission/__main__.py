"""`python -m user_permission` / `user-permission` CLI entrypoint.

The full-featured CLI lives in the Rust binary (``cargo install user-permission``).
This Python entrypoint mirrors the legacy ``user-permission serve`` interface
and delegates to ``user_permission.serve(...)``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from . import serve


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="user-permission",
        description="UserPermission – centralized user & group management",
    )
    sub = parser.add_subparsers(dest="command")

    serve_cmd = sub.add_parser("serve", help="Start the HTTP server")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8000)
    serve_cmd.add_argument("--database", default="user_permission.db")
    serve_cmd.add_argument("--secret", default="secret.key")
    serve_cmd.add_argument("--prefix", default="")
    serve_cmd.add_argument("--webui", action="store_true")
    serve_cmd.add_argument("--webui-prefix", default="/ui")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if args.command != "serve":
        _build_parser().print_help()
        sys.exit(1)

    # `serve(...)` calls into pyo3-async-runtimes which captures the running
    # asyncio loop at *evaluation* time. Building the awaitable inside an
    # `async def` ensures the loop is running by the time we reach it;
    # `asyncio.run(serve(...))` would fail with `no running event loop`
    # because the awaitable is constructed before `asyncio.run` starts.
    async def _run() -> None:
        await serve(
            host=args.host,
            port=args.port,
            database=args.database,
            secret=args.secret,
            prefix=args.prefix,
            webui=args.webui,
            webui_prefix=args.webui_prefix,
        )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
