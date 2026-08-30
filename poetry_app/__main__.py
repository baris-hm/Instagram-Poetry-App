"""Command-line entry point for the local application server."""

from __future__ import annotations

import argparse

from .server import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Şiirden Karelere prototype."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Address to bind to (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        default=8000,
        type=int,
        help="Port to listen on (default: 8000).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

