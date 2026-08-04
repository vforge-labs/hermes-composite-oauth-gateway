"""Command-line interface for the standalone Hermes OAuth proxy."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Sequence

from hermes_oauth_proxy.adapters import ADAPTERS, get_adapter
from hermes_oauth_proxy.server import DEFAULT_HOST, DEFAULT_PORT, run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hermes-oauth-proxy",
        description="Forward OpenAI-compatible requests using Hermes-managed OAuth credentials.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="run the proxy in the foreground")
    start.add_argument("--provider", choices=sorted(ADAPTERS), default="xai")
    start.add_argument("--host", default=DEFAULT_HOST)
    start.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub.add_parser("status", help="show adapter authentication readiness")
    sub.add_parser("providers", help="list available adapters")
    return parser


def _status() -> int:
    print("Hermes OAuth proxy upstream adapters")
    for name in sorted(ADAPTERS):
        adapter = get_adapter(name)
        if not adapter.is_authenticated():
            print(f"  [{name:12s}] {adapter.display_name} — not logged in")
            continue
        try:
            credential = adapter.get_credential()
        except Exception as exc:
            print(f"  [{name:12s}] {adapter.display_name} — credentials need attention ({exc})")
            continue
        expires = f" (bearer expires {credential.expires_at})" if credential.expires_at else ""
        print(f"  [{name:12s}] {adapter.display_name} — ready{expires}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "providers":
        for name in sorted(ADAPTERS):
            print(f"{name}\t{get_adapter(name).display_name}")
        return 0
    if args.command == "status":
        return _status()

    adapter = get_adapter(args.provider)
    if not adapter.is_authenticated():
        hint = getattr(adapter, "auth_hint", f"hermes auth add {adapter.name}")
        print(f"Not logged into {adapter.display_name}. Run `{hint}` first.", file=sys.stderr)
        return 2

    print(
        f"Starting Hermes OAuth proxy for {adapter.display_name}\n"
        f"  Listening on: http://{args.host}:{args.port}/v1\n"
        "  The client bearer is discarded; Hermes supplies the upstream credential.",
        file=sys.stderr,
    )
    try:
        asyncio.run(run_server(adapter, host=args.host, port=args.port))
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        print(f"proxy: failed to bind {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
