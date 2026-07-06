import argparse
from collections.abc import Callable
from pathlib import Path

from compatlab import __version__
from compatlab.bundle.resolver import DEFAULT_MAX_DEPTH, DEFAULT_MAX_FILES
from compatlab.diagnostics import FailOn
from compatlab.services.artifacts import (
    ArtifactCommandService,
    CompareCommandOptions,
    ScanCommandOptions,
)
from compatlab.services.profiles import ProfileCommandService


class CliServiceFactoryProtocol:
    def artifacts(self) -> ArtifactCommandService:
        raise NotImplementedError

    def profiles(self) -> ProfileCommandService:
        raise NotImplementedError


def existing_file(value: str) -> Path:
    path = Path(value)
    if not path.exists():
        raise argparse.ArgumentTypeError(f"Path does not exist: {value}")
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"Path is not a file: {value}")
    return path


def existing_dir(value: str) -> Path:
    path = Path(value)
    if not path.exists():
        raise argparse.ArgumentTypeError(f"Path does not exist: {value}")
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"Path is not a directory: {value}")
    return path


def path_arg(value: str) -> Path:
    return Path(value)


def fail_on_arg(value: str) -> FailOn:
    try:
        return FailOn(value)
    except ValueError as exc:
        choices = ", ".join(item for item in FailOn)
        raise argparse.ArgumentTypeError(
            f"invalid choice: {value!r} (choose from {choices})"
        ) from exc


def build_parser(services: CliServiceFactoryProtocol) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compatlab",
        description="Preflight compatibility checker for Linux binary artifacts.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"compatlab {__version__}",
        help="Show version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan one Linux artifact and print a structured stub report.",
        description="Scan one Linux artifact and print a structured stub report.",
    )
    _add_artifact_path(scan_parser)
    _add_bundle_options(scan_parser)
    _add_report_options(scan_parser)
    scan_parser.set_defaults(func=_scan_handler(services))

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare one Linux artifact with a target profile.",
        description="Compare one Linux artifact with a target profile.",
    )
    _add_artifact_path(compare_parser)
    compare_parser.add_argument("--target", help="Built-in profile id.")
    compare_parser.add_argument(
        "--target-file",
        type=path_arg,
        help="External YAML target profile.",
    )
    _add_bundle_options(compare_parser)
    _add_report_options(compare_parser)
    compare_parser.set_defaults(func=_compare_handler(services))

    profiles_parser = subparsers.add_parser(
        "profiles",
        help="Inspect built-in target profiles.",
        description="Inspect built-in target profiles.",
    )
    profiles_subparsers = profiles_parser.add_subparsers(dest="profiles_command", required=True)

    profiles_list_parser = profiles_subparsers.add_parser(
        "list",
        help="List built-in target profiles.",
        description="List built-in target profiles.",
    )
    profiles_list_parser.set_defaults(func=lambda _: services.profiles().list_profiles())

    profiles_show_parser = profiles_subparsers.add_parser(
        "show",
        help="Show one target profile.",
        description="Show one target profile.",
    )
    profiles_show_parser.add_argument("target", help="Built-in profile id or YAML path.")
    profiles_show_parser.set_defaults(
        func=lambda args: services.profiles().show_profile(args.target)
    )

    runtime_presets_parser = profiles_subparsers.add_parser(
        "runtime-presets",
        help="Inspect built-in Docker runtime presets.",
        description="Inspect built-in Docker runtime presets.",
    )
    runtime_subparsers = runtime_presets_parser.add_subparsers(
        dest="runtime_presets_command",
        required=True,
    )

    runtime_list_parser = runtime_subparsers.add_parser(
        "list",
        help="List built-in Docker runtime presets.",
        description="List built-in Docker runtime presets.",
    )
    runtime_list_parser.set_defaults(func=lambda _: services.profiles().list_runtime_presets())

    runtime_show_parser = runtime_subparsers.add_parser(
        "show",
        help="Show one Docker runtime preset.",
        description="Show one Docker runtime preset.",
    )
    runtime_show_parser.add_argument("name", help="Runtime preset name.")
    runtime_show_parser.set_defaults(
        func=lambda args: services.profiles().show_runtime_preset(args.name)
    )

    detect_parser = profiles_subparsers.add_parser(
        "detect",
        help="Detect raw facts from the current Linux system.",
        description="Detect raw facts from the current Linux system.",
    )
    _add_detection_options(detect_parser, json_help="Write raw detected system facts as JSON.")
    detect_parser.set_defaults(func=_profiles_detect_handler(services))

    generate_parser = profiles_subparsers.add_parser(
        "generate",
        help="Generate a YAML target profile.",
        description="Generate a YAML target profile.",
    )
    generate_parser.add_argument(
        "--from-current",
        action="store_true",
        help="Generate from the current Linux system.",
    )
    _add_detection_source_options(generate_parser, action="generation")
    generate_parser.add_argument(
        "--name",
        default="local",
        help="Generated target profile id.",
    )
    generate_parser.add_argument("--output", type=path_arg, help="Output YAML profile path.")
    generate_parser.set_defaults(func=_profiles_generate_handler(services))

    validate_parser = profiles_subparsers.add_parser(
        "validate",
        help="Validate a YAML target profile.",
        description="Validate a YAML target profile.",
    )
    validate_parser.add_argument("profile_file", type=path_arg, help="YAML target profile path.")
    validate_parser.add_argument(
        "--json",
        dest="json_output",
        type=path_arg,
        help="Write validation result as JSON.",
    )
    validate_parser.set_defaults(func=_profiles_validate_handler(services))

    return parser


def _add_artifact_path(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=existing_file)


def _add_bundle_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bundle-root", type=existing_dir)
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Resolve transitive bundled ELF dependencies.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=DEFAULT_MAX_DEPTH,
        help="Maximum recursive dependency depth.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=DEFAULT_MAX_FILES,
        help="Maximum files to index under bundle root.",
    )


def _add_report_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fail-on",
        type=fail_on_arg,
        default=FailOn.ERROR,
        help="Fail on diagnostics: error, warning, or never.",
    )
    parser.add_argument("--json", dest="json_output", type=path_arg, help="Write JSON report.")
    parser.add_argument(
        "--html",
        dest="html_output",
        type=path_arg,
        help="Write static HTML report.",
    )


def _add_detection_source_options(parser: argparse.ArgumentParser, *, action: str) -> None:
    parser.add_argument("--from-image", help="Detect raw facts from a Docker image.")
    parser.add_argument(
        "--platform",
        help="Docker image platform, for example linux/amd64.",
    )
    parser.add_argument("--pull", action="store_true", help=f"Pull Docker image before {action}.")
    parser.add_argument(
        "--runtime-preset",
        help=f"Install a built-in runtime preset before {action}.",
    )


def _add_detection_options(parser: argparse.ArgumentParser, *, json_help: str) -> None:
    _add_detection_source_options(parser, action="detection")
    parser.add_argument("--json", dest="json_output", type=path_arg, help=json_help)


def _scan_handler(
    services: CliServiceFactoryProtocol,
) -> Callable[[argparse.Namespace], None]:
    def handle(args: argparse.Namespace) -> None:
        services.artifacts().scan(
            ScanCommandOptions(
                path=args.path,
                bundle_root=args.bundle_root,
                recursive=args.recursive,
                max_depth=args.max_depth,
                max_files=args.max_files,
                fail_on=args.fail_on,
                json_output=args.json_output,
                html_output=args.html_output,
            )
        )

    return handle


def _compare_handler(
    services: CliServiceFactoryProtocol,
) -> Callable[[argparse.Namespace], None]:
    def handle(args: argparse.Namespace) -> None:
        services.artifacts().compare(
            CompareCommandOptions(
                path=args.path,
                target=args.target,
                target_file=args.target_file,
                bundle_root=args.bundle_root,
                recursive=args.recursive,
                max_depth=args.max_depth,
                max_files=args.max_files,
                fail_on=args.fail_on,
                json_output=args.json_output,
                html_output=args.html_output,
            )
        )

    return handle


def _profiles_detect_handler(
    services: CliServiceFactoryProtocol,
) -> Callable[[argparse.Namespace], None]:
    def handle(args: argparse.Namespace) -> None:
        services.profiles().detect(
            from_image=args.from_image,
            platform=args.platform,
            pull=args.pull,
            runtime_preset=args.runtime_preset,
            json_output=args.json_output,
        )

    return handle


def _profiles_generate_handler(
    services: CliServiceFactoryProtocol,
) -> Callable[[argparse.Namespace], None]:
    def handle(args: argparse.Namespace) -> None:
        services.profiles().generate(
            from_current=args.from_current,
            from_image=args.from_image,
            platform=args.platform,
            pull=args.pull,
            runtime_preset=args.runtime_preset,
            name=args.name,
            output=args.output,
        )

    return handle


def _profiles_validate_handler(
    services: CliServiceFactoryProtocol,
) -> Callable[[argparse.Namespace], None]:
    def handle(args: argparse.Namespace) -> None:
        services.profiles().validate(
            profile_file=args.profile_file,
            json_output=args.json_output,
        )

    return handle
