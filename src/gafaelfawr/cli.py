"""Administrative command-line interface."""

from __future__ import annotations

import sys
from typing import Optional, Union

import click
import structlog
import uvicorn
from kubernetes_asyncio.client import ApiClient
from safir.asyncio import run_with_asyncio
from safir.database import create_database_engine, initialize_database
from safir.kubernetes import initialize_kubernetes

from .dependencies.config import config_dependency
from .exceptions import KubernetesError
from .factory import ComponentFactory
from .keypair import RSAKeyPair
from .models.token import Token
from .schema import Base

__all__ = [
    "generate_key",
    "generate_token",
    "help",
    "init",
    "kubernetes_controller",
    "main",
    "run",
    "update_service_tokens",
]


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(message="%(version)s")
def main() -> None:
    """Gafaelfawr main.

    Administrative command-line interface for gafaelfawr.
    """
    pass


@main.command()
@click.argument("topic", default=None, required=False, nargs=1)
@click.pass_context
def help(ctx: click.Context, topic: Union[None, str]) -> None:
    """Show help for any command."""
    # The help command implementation is taken from
    # https://www.burgundywall.com/post/having-click-help-subcommand
    if topic:
        if topic in main.commands:
            click.echo(main.commands[topic].get_help(ctx))
        else:
            raise click.UsageError(f"Unknown help topic {topic}", ctx)
    else:
        assert ctx.parent
        click.echo(ctx.parent.get_help())


@main.command()
@click.option(
    "--port", default=8080, type=int, help="Port to run the application on."
)
def run(port: int) -> None:
    """Run the application (for testing only)."""
    uvicorn.run(
        "gafaelfawr.main:app", port=port, reload=True, reload_dirs=["src"]
    )


@main.command()
def generate_key() -> None:
    """Generate a new RSA key pair and print the private key."""
    keypair = RSAKeyPair.generate()
    print(keypair.private_key_as_pem())


@main.command()
def generate_token() -> None:
    """Generate an encoded token (such as the bootstrap token)."""
    print(str(Token()))


@main.command()
@click.option(
    "--settings",
    envvar="GAFAELFAWR_SETTINGS_PATH",
    type=str,
    default=None,
    help="Application settings file.",
)
@run_with_asyncio
async def init(settings: Optional[str]) -> None:
    """Initialize the database storage."""
    if settings:
        config_dependency.set_settings_path(settings)
    config = await config_dependency()
    logger = structlog.get_logger("gafaelfawr")
    engine = create_database_engine(
        config.database_url, config.database_password
    )
    await initialize_database(engine, logger, schema=Base.metadata)
    async with ComponentFactory.standalone(engine) as factory:
        admin_service = factory.create_admin_service()
        async with factory.session.begin():
            await admin_service.add_initial_admins(config.initial_admins)
        if config.firestore:
            firestore = factory.create_firestore_storage()
            await firestore.initialize()
    await engine.dispose()


@main.command()
@click.option(
    "--settings",
    envvar="GAFAELFAWR_SETTINGS_PATH",
    type=str,
    default=None,
    help="Application settings file.",
)
@run_with_asyncio
async def kubernetes_controller(settings: Optional[str]) -> None:
    if settings:
        config_dependency.set_settings_path(settings)
    config = await config_dependency()
    logger = structlog.get_logger("gafaelfawr")
    logger.debug("Starting")
    engine = create_database_engine(
        config.database_url, config.database_password
    )
    async with ComponentFactory.standalone(engine, check_db=True) as factory:
        await initialize_kubernetes()
        async with ApiClient() as api_client:
            kubernetes_service = factory.create_kubernetes_service(api_client)
            logger.debug("Updating all service tokens")
            await kubernetes_service.update_service_tokens()
            logger.debug("Starting Kubernetes watcher")
            queue = await kubernetes_service.start_watcher()
            logger.debug("Starting continuous processing")
            await kubernetes_service.update_service_tokens_from_queue(queue)


@main.command()
@click.option(
    "--settings",
    envvar="GAFAELFAWR_SETTINGS_PATH",
    type=str,
    default=None,
    help="Application settings file.",
)
@run_with_asyncio
async def update_service_tokens(settings: Optional[str]) -> None:
    """Update service tokens stored in Kubernetes secrets."""
    if settings:
        config_dependency.set_settings_path(settings)
    config = await config_dependency()
    logger = structlog.get_logger("gafaelfawr")
    engine = create_database_engine(
        config.database_url, config.database_password
    )
    async with ComponentFactory.standalone(engine, check_db=True) as factory:
        await initialize_kubernetes()
        async with ApiClient() as api_client:
            kubernetes_service = factory.create_kubernetes_service(api_client)
            try:
                logger.debug("Updating all service tokens")
                await kubernetes_service.update_service_tokens()
            except KubernetesError as e:
                msg = "Failed to update service token secrets"
                logger.error(msg, error=str(e))
                sys.exit(1)
