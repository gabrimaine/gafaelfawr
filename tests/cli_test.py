"""Tests for the command-line interface.

Be careful when writing tests in this framework because the click command
handling code spawns its own async worker pools when needed.  You therefore
cannot use the ``setup`` fixture here because the two thread pools will
conflict with each other.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import structlog
from _pytest.logging import LogCaptureFixture
from click.testing import CliRunner
from kubernetes_asyncio.client import ApiException
from safir.database import initialize_database
from safir.testing.kubernetes import MockKubernetesApi

from gafaelfawr.cli import main
from gafaelfawr.config import Config
from gafaelfawr.factory import ComponentFactory
from gafaelfawr.models.admin import Admin
from gafaelfawr.models.token import Token, TokenData
from gafaelfawr.schema import Base

from .support.logging import parse_log


async def _initialize_database(config: Config) -> None:
    """Helper function to initialize the database."""
    logger = structlog.get_logger(config.safir.logger_name)
    engine = await initialize_database(
        config.database_url,
        config.database_password,
        logger,
        schema=Base.metadata,
        reset=True,
    )
    await engine.dispose()


def test_generate_key() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["generate-key"])

    assert result.exit_code == 0
    assert "-----BEGIN PRIVATE KEY-----" in result.output


def test_generate_token() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["generate-token"])

    assert result.exit_code == 0
    assert Token.from_str(result.output.rstrip("\n"))


def test_help() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["-h"])
    assert result.exit_code == 0
    assert "Commands:" in result.output

    result = runner.invoke(main, ["help"])
    assert result.exit_code == 0
    assert "Commands:" in result.output

    result = runner.invoke(main, ["help", "run"])
    assert result.exit_code == 0
    assert "Options:" in result.output
    assert "Commands:" not in result.output

    result = runner.invoke(main, ["help", "unknown-command"])
    assert result.exit_code != 0
    assert "Unknown help topic unknown-command" in result.output


def test_init(config: Config) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0

    # We can't make the test async or its loop will interfere with the one
    # created by gafaelfawr.cli, so instead use asyncio.run to run a check
    # that the database schema is present.
    async def check_database() -> None:
        async with ComponentFactory.standalone() as factory:
            admin_service = factory.create_admin_service()
            expected = [Admin(username=u) for u in config.initial_admins]
            assert await admin_service.get_admins() == expected
            token_service = factory.create_token_service()
            bootstrap = TokenData.bootstrap_token()
            assert await token_service.list_tokens(bootstrap) == []

    asyncio.run(check_database())


def test_update_service_tokens(
    tmp_path: Path, config: Config, mock_kubernetes: MockKubernetesApi
) -> None:
    asyncio.run(_initialize_database(config))
    asyncio.run(
        mock_kubernetes.create_namespaced_custom_object(
            "gafaelfawr.lsst.io",
            "v1alpha1",
            "mobu",
            "gafaelfawrservicetokens",
            {
                "apiVersion": "gafaelfawr.lsst.io/v1alpha1",
                "kind": "GafaelfawrServiceToken",
                "metadata": {
                    "name": "gafaelfawr-secret",
                    "namespace": "mobu",
                    "generation": 1,
                },
                "spec": {
                    "service": "mobu",
                    "scopes": ["admin:token"],
                },
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(main, ["update-service-tokens"])

    assert result.exit_code == 0
    assert mock_kubernetes.get_all_objects_for_test("Secret")


def test_update_service_tokens_error(
    tmp_path: Path,
    config: Config,
    mock_kubernetes: MockKubernetesApi,
    caplog: LogCaptureFixture,
) -> None:
    asyncio.run(_initialize_database(config))
    caplog.clear()

    def error_callback(method: str, *args: Any) -> None:
        if method == "list_cluster_custom_object":
            raise ApiException(status=500, reason="Some error")

    mock_kubernetes.error_callback = error_callback
    runner = CliRunner()
    result = runner.invoke(main, ["update-service-tokens"])

    assert result.exit_code == 1
    assert parse_log(caplog) == [
        {
            "event": "Unable to list GafaelfawrServiceToken objects",
            "error": "Kubernetes API error: (500)\nReason: Some error\n",
            "severity": "error",
        },
        {
            "error": "Kubernetes API error: (500)\nReason: Some error\n",
            "event": "Failed to update service token secrets",
            "severity": "error",
        },
    ]
