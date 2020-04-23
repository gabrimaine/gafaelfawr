"""Tests for the /login route with OpenID Connect."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import ANY
from urllib.parse import parse_qs, urlparse

from gafaelfawr.constants import ALGORITHM

if TYPE_CHECKING:
    from tests.setup import SetupTestCallable


async def test_login(create_test_setup: SetupTestCallable) -> None:
    setup = await create_test_setup("oidc")
    assert setup.config.oidc

    # Simulate the initial authentication request.
    return_url = f"https://{setup.client.host}:4444/foo?a=bar&b=baz"
    r = await setup.client.get(
        "/login", params={"rd": return_url}, allow_redirects=False,
    )
    assert r.status == 303
    assert r.headers["Location"].startswith(setup.config.oidc.login_url)
    url = urlparse(r.headers["Location"])
    assert url.query
    query = parse_qs(url.query)
    login_params = {p: [v] for p, v in setup.config.oidc.login_params.items()}
    assert query == {
        "client_id": [setup.config.oidc.client_id],
        "redirect_uri": [setup.config.oidc.redirect_url],
        "response_type": ["code"],
        "scope": ["openid " + " ".join(setup.config.oidc.scopes)],
        "state": [ANY],
        **login_params,
    }

    # Simulate the return from the provider.
    r = await setup.client.get(
        "/login",
        params={"code": "some-code", "state": query["state"][0]},
        allow_redirects=False,
    )
    assert r.status == 303
    assert r.headers["Location"] == return_url

    # Check that the /auth route works and finds our token.
    r = await setup.client.get("/auth", params={"scope": "exec:admin"})
    assert r.status == 200
    assert r.headers["X-Auth-Request-Token-Scopes"] == "exec:admin read:all"
    assert r.headers["X-Auth-Request-Scopes-Accepted"] == "exec:admin"
    assert r.headers["X-Auth-Request-Scopes-Satisfy"] == "all"
    assert r.headers["X-Auth-Request-Email"] == "some-user@example.com"
    assert r.headers["X-Auth-Request-User"] == "some-user"
    assert r.headers["X-Auth-Request-Uid"] == "1000"
    assert r.headers["X-Auth-Request-Groups"] == "admin"
    assert r.headers["X-Auth-Request-Token"]

    # Now ask for the session handle in the encrypted session to be analyzed,
    # and verify the internals of the session handle from OpenID Connect
    # authentication.
    r = await setup.client.get("/auth/analyze")
    assert r.status == 200
    data = await r.json()
    assert data == {
        "handle": {"key": ANY, "secret": ANY},
        "session": {
            "email": "some-user@example.com",
            "created_at": ANY,
            "expires_on": ANY,
        },
        "token": {
            "header": {
                "alg": ALGORITHM,
                "typ": "JWT",
                "kid": setup.config.issuer.kid,
            },
            "data": {
                "act": {
                    "aud": setup.config.oidc.audience,
                    "iss": setup.config.oidc.issuer,
                    "jti": ANY,
                },
                "aud": setup.config.issuer.aud,
                "email": "some-user@example.com",
                "exp": ANY,
                "iat": ANY,
                "isMemberOf": [{"name": "admin"}],
                "iss": setup.config.issuer.iss,
                "jti": ANY,
                "scope": "exec:admin read:all",
                "sub": "some-user",
                "uid": "some-user",
                "uidNumber": "1000",
            },
            "valid": True,
        },
    }


async def test_login_redirect_header(
    create_test_setup: SetupTestCallable,
) -> None:
    """Test receiving the redirect header via X-Auth-Request-Redirect."""
    setup = await create_test_setup("oidc")

    # Simulate the initial authentication request.
    return_url = f"https://{setup.client.host}/foo?a=bar&b=baz"
    r = await setup.client.get(
        "/login",
        headers={"X-Auth-Request-Redirect": return_url},
        allow_redirects=False,
    )
    assert r.status == 303
    url = urlparse(r.headers["Location"])
    query = parse_qs(url.query)

    # Simulate the return from the OpenID Connect provider.
    r = await setup.client.get(
        "/login",
        params={"code": "some-code", "state": query["state"][0]},
        allow_redirects=False,
    )
    assert r.status == 303
    assert r.headers["Location"] == return_url


async def test_oauth2_callback(create_test_setup: SetupTestCallable) -> None:
    """Test the compatibility /oauth2/callback route."""
    setup = await create_test_setup("oidc")
    assert setup.config.oidc

    # Simulate the initial authentication request.
    return_url = f"https://{setup.client.host}/foo"
    r = await setup.client.get(
        "/login", params={"rd": return_url}, allow_redirects=False,
    )
    assert r.status == 303
    url = urlparse(r.headers["Location"])
    query = parse_qs(url.query)
    assert query["redirect_uri"][0] == setup.config.oidc.redirect_url

    # Simulate the return from the OpenID Connect provider.
    r = await setup.client.get(
        "/oauth2/callback",
        params={"code": "some-code", "state": query["state"][0]},
        allow_redirects=False,
    )
    assert r.status == 303
    assert r.headers["Location"] == return_url
