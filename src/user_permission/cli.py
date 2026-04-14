from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="user-permission",
        description="UserPermission – centralized user & group management",
    )
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Start the HTTP server")
    serve.add_argument(
        "--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)"
    )
    serve.add_argument(
        "--port", type=int, default=8000, help="Bind port (default: 8000)"
    )
    serve.add_argument(
        "--database",
        default="user_permission.db",
        help="SQLite database path (default: user_permission.db)",
    )
    serve.add_argument(
        "--secret",
        default="secret.key",
        help="Secret-key file path (default: secret.key)",
    )
    serve.add_argument(
        "--prefix", default="", help="API route prefix (e.g. /api)"
    )
    serve.add_argument(
        "--webui",
        action="store_true",
        help="HTMX + Tailwind + Jinja2 の管理画面を有効化する",
    )
    serve.add_argument(
        "--webui-prefix",
        default="/ui",
        help="管理画面のURLプレフィックス (default: /ui)",
    )

    args = parser.parse_args()

    if args.command == "serve":
        _run_serve(args)
    else:
        parser.print_help()
        sys.exit(1)


def _run_serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn  # type: ignore[import-untyped]
    except ImportError:
        print(
            "uvicorn is required to run the server.\n"
            "Install with:  pip install user-permission[server]",
            file=sys.stderr,
        )
        sys.exit(1)

    from .server import create_app

    app = create_app(
        database=args.database,
        secret=args.secret,
        prefix=args.prefix,
        webui=args.webui,
        webui_prefix=args.webui_prefix,
    )
    uvicorn.run(app, host=args.host, port=args.port)
