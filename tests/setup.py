"""Set up the test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gafaelfawr.session import Session, SessionHandle
from tests.support.tokens import create_oidc_test_token, create_test_token

if TYPE_CHECKING:
    from aiohttp import web
    from aiohttp.pytest_plugin.test_utils import TestClient
    from aioredis import Redis
    from gafaelfawr.config import Config
    from gafaelfawr.factory import ComponentFactory
    from gafaelfawr.tokens import VerifiedToken
    from typing import Awaitable, Callable, List, Optional


class SetupTest:
    """Utility class for test setup.

    This class wraps creating a test aiohttp application, creating a factory
    for building the JWT Authorizer components, and accessing configuration
    settings.
    """

    def __init__(self, app: web.Application, client: TestClient) -> None:
        self.app = app
        self.client = client
        self.config: Config = self.app["gafaelfawr/config"]
        self.factory: ComponentFactory = self.app["gafaelfawr/factory"]
        self.redis: Redis = self.app["gafaelfawr/redis"]

    async def create_session(
        self, *, groups: Optional[List[str]] = None, **claims: str
    ) -> SessionHandle:
        """Create a session from a new signed internal token.

        Create a signed internal token as with create_token, but immediately
        store it in a session and return the corresponding session handle.

        Parameters
        ----------
        groups : List[`str`], optional
            Group memberships the generated token should have.
        **claims : `str`, optional
            Other claims to set or override in the token.

        Returns
        -------
        handle : `gafaelfawr.session.SessionHandle`
            The new session handle.
        """
        handle = SessionHandle()
        token = self.create_token(groups=groups, jti=handle.key, **claims)
        session = Session.create(handle, token)
        session_store = self.factory.create_session_store()
        await session_store.store_session(session)
        return handle

    def create_token(
        self, *, groups: Optional[List[str]] = None, **claims: str
    ) -> VerifiedToken:
        """Create a signed internal token.

        Parameters
        ----------
        groups : List[`str`], optional
            Group memberships the generated token should have.
        **claims : `str`, optional
            Other claims to set or override in the token.

        Returns
        -------
        token : `gafaelfawr.tokens.VerifiedToken`
            The generated token.
        """
        return create_test_token(self.config, groups=groups, **claims)

    def create_oidc_token(
        self, *, groups: Optional[List[str]] = None, **claims: str
    ) -> VerifiedToken:
        """Create a signed OpenID Connect token.

        Parameters
        ----------
        groups : List[`str`], optional
            Group memberships the generated token should have.
        **claims : `str`, optional
            Other claims to set or override in the token.

        Returns
        -------
        token : `gafaelfawr.tokens.VerifiedToken`
            The generated token.
        """
        return create_oidc_test_token(self.config, groups=groups, **claims)


# Type of the pytest fixture that builds the SetupTest object.
if TYPE_CHECKING:
    SetupTestCallable = Callable[..., Awaitable[SetupTest]]
