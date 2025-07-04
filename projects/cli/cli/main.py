# main.py
import asyncio
import sys

import click

from cli.config import load_config
from cli.log import setup_logging
from cli.monitor import monitor_main
from cli.mythic_connector.mythic_connector import start
from cli.stage1_connector.stage1_connector import run_outflank_connector
from cli.submit import submit_main


def get_default_config_file(tool_name: str) -> str:
    """Get the default configuration file for a given tool"""
    if tool_name == "outflank":
        return "settings_outflank.yaml"
    elif tool_name == "mythic":
        return "settings_mythic.yaml"
    else:
        raise ValueError(f"Unknown tool name: {tool_name}")


# Common options for commands that need config
def connector_options(tool_name: str):
    """Decorator factory to add common options for connector commands"""

    def decorator(f):
        f = click.option(
            "--showconfig",
            is_flag=True,
            help="Display an example configuration file and exit",
        )(f)

        f = click.option(
            "--debug",
            is_flag=True,
            help="Enable debug logging",
            default=False,
            show_default=True,
        )(f)

        f = click.option(
            "--config",
            "-c",
            type=click.Path(exists=True, dir_okay=False, path_type=str),
            default=get_default_config_file(tool_name),
            help="Path to YAML config file",
            show_default=True,
        )(f)

        return f

    return decorator


@click.group(context_settings={"max_content_width": 120})
def cli():
    """Nemesis CLI - Interact with the Nemesis platform"""
    pass


@cli.command()
@connector_options("outflank")
def connect_outflank(config: str, debug: bool, showconfig: bool):
    """Ingest Outflank C2 data into Nemesis"""

    if showconfig:
        with open(config) as f:
            click.echo(f.read())
        sys.exit(0)

    logger = setup_logging(debug)
    try:
        # get the absolute path of the config file
        abs_path = click.format_filename(config)

        logger.info("Starting Outflank connector using the config file: %s", abs_path)
        cfg = load_config(config)
        asyncio.run(run_outflank_connector(cfg, logger))
    except Exception as e:
        logger.exception("Unhandled exception in connector", e)
        sys.exit(1)


@cli.command()
@connector_options("mythic")
def connect_mythic(config: str, debug: bool, showconfig: bool) -> None:
    """Mythic Sync - Synchronize data between Mythic and Nemesis."""

    if showconfig:
        with open(config) as f:
            click.echo(f.read())
        sys.exit(0)

    try:
        asyncio.run(start(config, debug))
    except KeyboardInterrupt:
        click.echo("Interrupted by user, shutting down...")
    except Exception as e:
        click.echo(f"Unexpected error: {e}")
        raise click.Abort() from e


def get_os_user_and_host_string() -> str:
    """Get the current OS user and hostname for metadata"""
    import os
    import socket

    user = os.getenv("USER") or os.getenv("USERNAME") or "unknown_user"
    host = socket.gethostname() or "unknown_host"
    return f"{user}@{host}"


@cli.command()
@click.argument("paths", type=click.Path(exists=True), nargs=-1, required=True, metavar="PATHS...")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("-h", "--host", default="0.0.0.0:7443", help="Host and port in format HOST:PORT", show_default=True)
@click.option("-r", "--recursive", is_flag=True, default=False, help="Recursively process subdirectories")
@click.option("-w", "--workers", default=10, help="Number of worker threads", show_default=True)
@click.option("-u", "--username", default="n", help="Basic auth username", show_default=True)
@click.option("-p", "--password", default="n", help="Basic auth password", show_default=True)
@click.option("--project", default="assess-test", help="Project name for metadata", show_default=True)
@click.option(
    "--agent-id", default=("submit" + get_os_user_and_host_string()), help="Agent ID for metadata", show_default=True
)
@click.option(
    "-f",
    "--file",
    "file_path",
    type=click.Path(exists=True, dir_okay=False, path_type=str),
    help="Path to single file to submit (alternative to PATHS for backwards compatibility)",
)
def submit(
    debug: bool,
    paths: tuple[str, ...],
    host: str,
    recursive: bool,
    workers: int,
    username: str,
    password: str,
    project: str,
    agent_id: str,
    file_path: str,
):
    """Submit files to Nemesis for processing"""
    submit_main(
        debug,
        paths,
        host,
        recursive,
        workers,
        username,
        password,
        project,
        agent_id,
        file_path,
    )


@cli.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True), required=True)
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("-h", "--host", default="0.0.0.0:7443", help="Host and port in format HOST:PORT", show_default=True)
@click.option("-u", "--username", default="n", help="Basic auth username", show_default=True)
@click.option("-p", "--password", default="n", help="Basic auth password", show_default=True)
@click.option("--project", default="assess-test", help="Project name for metadata", show_default=True)
@click.option(
    "--agent-id", default=("monitor" + get_os_user_and_host_string()), help="Agent ID for metadata", show_default=True
)
@click.option("-w", "--workers", default=10, help="Number of worker threads for initial submission", show_default=True)
@click.option("--only-monitor", is_flag=True, help="Only monitor for new files, don't submit existing files")
def monitor(
    path: str,
    debug: bool,
    host: str,
    username: str,
    password: str,
    project: str,
    agent_id: str,
    workers: int,
    only_monitor: bool,
):
    """Monitor a folder for new files and submit them to Nemesis"""
    monitor_main(
        path,
        debug,
        host,
        username,
        password,
        project,
        agent_id,
        only_monitor,
        workers,
    )


def main():
    """Entry point for the CLI"""
    cli()


if __name__ == "__main__":
    main()
