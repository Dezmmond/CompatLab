import sys
from collections.abc import Sequence

from rich.console import Console

from compatlab.arg_parser import build_parser
from compatlab.services.artifacts import ArtifactCommandService
from compatlab.services.exceptions import CommandExit
from compatlab.services.profiles import ProfileCommandService


class CliServiceFactoryProtocol:
    @staticmethod
    def artifacts() -> ArtifactCommandService:
        return ArtifactCommandService(console=console)

    @staticmethod
    def profiles() -> ProfileCommandService:
        return ProfileCommandService(console=console)


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser(services)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except CommandExit as exc:
        return exc.code
    return 0


def main(argv: Sequence[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    raise SystemExit(run(argv))


console = Console()
services = CliServiceFactoryProtocol()

app = main


if __name__ == "__main__":
    main(sys.argv[1:])
