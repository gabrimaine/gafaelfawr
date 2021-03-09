"""Route handlers for the ``/auth/api/v1`` API.

All the route handlers are intentionally defined in a single file to encourage
the implementation to be very short.  All the business logic should be defined
in manager objects and the output formatting should be handled by response
models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)

from gafaelfawr.constants import ACTOR_REGEX, CURSOR_REGEX, USERNAME_REGEX
from gafaelfawr.dependencies.auth import AuthenticateRead, AuthenticateWrite
from gafaelfawr.dependencies.context import RequestContext, context_dependency
from gafaelfawr.exceptions import ErrorLocation, NotFoundError
from gafaelfawr.models.admin import Admin
from gafaelfawr.models.auth import APIConfig, APILoginResponse, Scope
from gafaelfawr.models.error import ErrorModel
from gafaelfawr.models.history import TokenChangeHistoryEntry
from gafaelfawr.models.token import (
    AdminTokenRequest,
    NewToken,
    TokenData,
    TokenInfo,
    TokenType,
    TokenUserInfo,
    UserTokenModifyRequest,
    UserTokenRequest,
)
from gafaelfawr.util import random_128_bits

__all__ = ["router"]

router = APIRouter()
authenticate_read = AuthenticateRead()
authenticate_write = AuthenticateWrite()
authenticate_admin_read = AuthenticateRead(
    require_scope="admin:token", allow_bootstrap_token=True
)
authenticate_admin_write = AuthenticateWrite(
    require_scope="admin:token", allow_bootstrap_token=True
)
authenticate_session_read = AuthenticateRead(require_session=True)


@router.get(
    "/admins",
    dependencies=[Depends(authenticate_admin_read)],
    response_model=List[Admin],
    summary="List all administrators",
    tags=["admin"],
)
def get_admins(
    context: RequestContext = Depends(context_dependency),
) -> List[Admin]:
    admin_service = context.factory.create_admin_service()
    return admin_service.get_admins()


@router.post(
    "/admins",
    status_code=204,
    summary="Add new administrator",
    tags=["admin"],
)
def add_admin(
    admin: Admin,
    auth_data: TokenData = Depends(authenticate_admin_write),
    context: RequestContext = Depends(context_dependency),
) -> None:
    admin_service = context.factory.create_admin_service()
    admin_service.add_admin(
        admin.username,
        actor=auth_data.username,
        ip_address=context.request.client.host,
    )


@router.delete(
    "/admins/{username}",
    responses={
        403: {"description": "Permission denied", "model": ErrorModel},
        404: {"description": "Specified user is not an administrator"},
    },
    status_code=204,
    summary="Delete an administrator",
    tags=["admin"],
)
def delete_admin(
    username: str = Path(
        ...,
        title="Administrator",
        description="Username of administrator to delete",
        example="adminuser",
        min_length=1,
        max_length=64,
        regex=USERNAME_REGEX,
    ),
    auth_data: TokenData = Depends(authenticate_admin_write),
    context: RequestContext = Depends(context_dependency),
) -> None:
    admin_service = context.factory.create_admin_service()
    success = admin_service.delete_admin(
        username,
        actor=auth_data.username,
        ip_address=context.request.client.host,
    )
    if not success:
        msg = "Specified user is not an administrator"
        raise NotFoundError(msg, ErrorLocation.path, "username")


@router.get(
    "/history/token-changes",
    description=(
        "Get the change history of tokens for any user. If a limit or cursor"
        " was specified, links to paginated results may be found in the Link"
        " header of the reply and the total number of records in the"
        " X-Total-Count header."
    ),
    response_model=List[TokenChangeHistoryEntry],
    response_model_exclude_unset=True,
    summary="Get token change history",
    tags=["admin"],
)
def get_admin_token_change_history(
    response: Response,
    cursor: Optional[str] = Query(
        None,
        title="Cursor",
        description="Pagination cursor",
        example="1614985055_4234",
        regex=CURSOR_REGEX,
    ),
    limit: Optional[int] = Query(
        None,
        title="Row limit",
        description="Maximum number of entries to return",
        example=500,
        ge=1,
    ),
    since: Optional[datetime] = Query(
        None,
        title="Not before",
        description="Only show entries at or after this time",
        example="2021-03-05T14:59:52Z",
    ),
    until: Optional[datetime] = Query(
        None,
        title="Not after",
        description="Only show entries before or at this time",
        example="2021-03-05T14:59:52Z",
    ),
    username: Optional[str] = Query(
        None,
        title="Username",
        description="Only show tokens for this user",
        example="someuser",
        min_length=1,
        max_length=64,
        regex=USERNAME_REGEX,
    ),
    actor: Optional[str] = Query(
        None,
        title="Actor",
        description="Only show actions performed by this user",
        example="adminuser",
        min_length=1,
        max_length=64,
        regex=ACTOR_REGEX,
    ),
    key: Optional[str] = Query(
        None,
        title="Token",
        description="Only show changes for this token",
        example="dDQg_NTNS51GxeEteqnkag",
        min_length=22,
        max_length=22,
    ),
    token_type: Optional[TokenType] = Query(
        None,
        title="Token type",
        description="Only show tokens of this type",
        example="user",
    ),
    ip_address: Optional[str] = Query(
        None,
        title="IP or CIDR",
        description="Only show changes from this IP or CIDR block",
        example="198.51.100.0/24",
    ),
    auth_data: TokenData = Depends(authenticate_admin_read),
    context: RequestContext = Depends(context_dependency),
) -> List[Dict[str, Any]]:
    token_service = context.factory.create_token_service()
    results = token_service.get_change_history(
        auth_data,
        cursor=cursor,
        limit=limit,
        since=since,
        until=until,
        username=username,
        actor=actor,
        key=key,
        token_type=token_type,
        ip_or_cidr=ip_address,
    )
    if limit:
        response.headers["Link"] = results.link_header(context.request.url)
        response.headers["X-Total-Count"] = str(results.count)
    return [r.reduced_dict() for r in results.entries]


@router.get(
    "/login",
    description=(
        "Used by the JavaScript UI to obtain a CSRF token, user metadata,"
        " and server configuration. Not used with regular API calls."
    ),
    response_model=APILoginResponse,
    summary="Initialize UI",
    tags=["browser"],
)
def get_login(
    auth_data: TokenData = Depends(authenticate_session_read),
    context: RequestContext = Depends(context_dependency),
) -> APILoginResponse:
    if not context.state.csrf:
        context.state.csrf = random_128_bits()
    known_scopes = [
        Scope(name=n, description=d)
        for n, d in sorted(context.config.known_scopes.items())
    ]
    api_config = APIConfig(scopes=known_scopes)
    return APILoginResponse(
        csrf=context.state.csrf,
        username=auth_data.username,
        scopes=auth_data.scopes,
        config=api_config,
    )


@router.get(
    "/token-info",
    description="Return metadata about the authentication token",
    response_model=TokenInfo,
    response_model_exclude_none=True,
    responses={404: {"description": "Token not found", "model": ErrorModel}},
    summary="Get token details",
    tags=["user"],
)
async def get_token_info(
    auth_data: TokenData = Depends(authenticate_read),
    context: RequestContext = Depends(context_dependency),
) -> TokenInfo:
    token_service = context.factory.create_token_service()
    info = token_service.get_token_info_unchecked(auth_data.token.key)
    if info:
        return info
    else:
        msg = "Token found in Redis but not database"
        context.logger.warning(msg)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=[{"type": "invalid_token", "msg": msg}],
        )


@router.post(
    "/tokens",
    response_model=NewToken,
    status_code=201,
    summary="Create a token",
    tags=["admin"],
)
async def post_admin_tokens(
    token_request: AdminTokenRequest,
    response: Response,
    auth_data: TokenData = Depends(authenticate_admin_write),
    context: RequestContext = Depends(context_dependency),
) -> NewToken:
    token_service = context.factory.create_token_service()
    token = await token_service.create_token_from_admin_request(
        token_request,
        auth_data,
        ip_address=context.request.client.host,
    )
    response.headers["Location"] = quote(
        f"/auth/api/v1/users/{token_request.username}/tokens/{token.key}"
    )
    return NewToken(token=str(token))


@router.get(
    "/user-info",
    description="Get metadata about the autheticated user",
    response_model=TokenUserInfo,
    response_model_exclude_none=True,
    summary="Get user metadata",
    tags=["user"],
)
async def get_user_info(
    auth_data: TokenData = Depends(authenticate_read),
) -> TokenUserInfo:
    return auth_data


@router.get(
    "/users/{username}/token-change-history",
    description=(
        "Get the change history of tokens for the current user. If a limit"
        " or cursor was specified, links to paginated results may be found"
        " in the Link header of the reply and the total number of records"
        " in the X-Total-Count header."
    ),
    response_model=List[TokenChangeHistoryEntry],
    response_model_exclude_unset=True,
    summary="Get token change history",
    tags=["user"],
)
def get_user_token_change_history(
    response: Response,
    username: str = Path(
        ...,
        title="Username",
        example="someuser",
        min_length=1,
        max_length=64,
        regex=USERNAME_REGEX,
    ),
    cursor: Optional[str] = Query(
        None,
        title="Cursor",
        description="Pagination cursor",
        example="1614985055_4234",
        regex=CURSOR_REGEX,
    ),
    limit: Optional[int] = Query(
        None,
        title="Row limit",
        description="Maximum number of entries to return",
        example=500,
        ge=1,
    ),
    since: Optional[datetime] = Query(
        None,
        title="Not before",
        description="Only show entries at or after this time",
        example="2021-03-05T14:59:52Z",
    ),
    until: Optional[datetime] = Query(
        None,
        title="Not after",
        description="Only show entries before or at this time",
        example="2021-03-05T14:59:52Z",
    ),
    key: Optional[str] = Query(
        None,
        title="Token",
        description="Only show changes for this token",
        example="dDQg_NTNS51GxeEteqnkag",
        min_length=22,
        max_length=22,
    ),
    token_type: Optional[TokenType] = Query(
        None,
        title="Token type",
        description="Only show tokens of this type",
        example="user",
    ),
    ip_address: Optional[str] = Query(
        None,
        title="IP or CIDR",
        description="Only show changes from this IP or CIDR block",
        example="198.51.100.0/24",
    ),
    auth_data: TokenData = Depends(authenticate_read),
    context: RequestContext = Depends(context_dependency),
) -> List[Dict[str, Any]]:
    token_service = context.factory.create_token_service()
    results = token_service.get_change_history(
        auth_data,
        cursor=cursor,
        username=username,
        limit=limit,
        since=since,
        until=until,
        key=key,
        token_type=token_type,
        ip_or_cidr=ip_address,
    )
    if limit:
        response.headers["Link"] = results.link_header(context.request.url)
        response.headers["X-Total-Count"] = str(results.count)
    return [r.reduced_dict() for r in results.entries]


@router.get(
    "/users/{username}/tokens",
    response_model=List[TokenInfo],
    response_model_exclude_none=True,
    summary="List tokens",
    tags=["user"],
)
async def get_tokens(
    username: str = Path(
        ...,
        title="Username",
        example="someuser",
        min_length=1,
        max_length=64,
        regex=USERNAME_REGEX,
    ),
    auth_data: TokenData = Depends(authenticate_read),
    context: RequestContext = Depends(context_dependency),
) -> List[TokenInfo]:
    token_service = context.factory.create_token_service()
    return token_service.list_tokens(auth_data, username)


@router.post(
    "/users/{username}/tokens",
    response_model=NewToken,
    status_code=201,
    summary="Create user token",
    tags=["user"],
)
async def post_tokens(
    token_request: UserTokenRequest,
    response: Response,
    username: str = Path(
        ...,
        title="Username",
        example="someuser",
        min_length=1,
        max_length=64,
        regex=USERNAME_REGEX,
    ),
    auth_data: TokenData = Depends(authenticate_write),
    context: RequestContext = Depends(context_dependency),
) -> NewToken:
    token_service = context.factory.create_token_service()
    token_params = token_request.dict()
    token = await token_service.create_user_token(
        auth_data,
        username,
        ip_address=context.request.client.host,
        **token_params,
    )
    response.headers["Location"] = quote(
        f"/auth/api/v1/users/{username}/tokens/{token.key}"
    )
    return NewToken(token=str(token))


@router.get(
    "/users/{username}/tokens/{key}",
    response_model=TokenInfo,
    response_model_exclude_none=True,
    responses={404: {"description": "Token not found", "model": ErrorModel}},
    summary="Get token metadata",
    tags=["user"],
)
async def get_token(
    username: str = Path(
        ...,
        title="Username",
        example="someuser",
        min_length=1,
        max_length=64,
        regex=USERNAME_REGEX,
    ),
    key: str = Path(
        ...,
        title="Token key",
        example="GpbIL3_qhgZlpfGTFF",
        min_length=22,
        max_length=22,
    ),
    auth_data: TokenData = Depends(authenticate_write),
    context: RequestContext = Depends(context_dependency),
) -> TokenInfo:
    token_service = context.factory.create_token_service()
    info = token_service.get_token_info(key, auth_data, username)
    if info:
        return info
    else:
        raise NotFoundError("Token not found", ErrorLocation.path, "key")


@router.delete(
    "/users/{username}/tokens/{key}",
    responses={404: {"description": "Token not found", "model": ErrorModel}},
    summary="Revoke token",
    status_code=204,
    tags=["user"],
)
async def delete_token(
    username: str = Path(
        ...,
        title="Username",
        example="someuser",
        min_length=1,
        max_length=64,
        regex=USERNAME_REGEX,
    ),
    key: str = Path(
        ...,
        title="Token key",
        example="GpbIL3_qhgZlpfGTFF",
        min_length=22,
        max_length=22,
    ),
    auth_data: TokenData = Depends(authenticate_write),
    context: RequestContext = Depends(context_dependency),
) -> None:
    token_service = context.factory.create_token_service()
    success = await token_service.delete_token(
        key,
        auth_data,
        username,
        ip_address=context.request.client.host,
    )
    if not success:
        raise NotFoundError("Token not found", ErrorLocation.path, "key")


@router.patch(
    "/users/{username}/tokens/{key}",
    response_model=TokenInfo,
    response_model_exclude_none=True,
    responses={404: {"description": "Token not found", "model": ErrorModel}},
    status_code=201,
    summary="Modify user token",
    tags=["user"],
)
async def patch_token(
    token_request: UserTokenModifyRequest,
    username: str = Path(
        ...,
        title="Username",
        example="someuser",
        min_length=1,
        max_length=64,
        regex=USERNAME_REGEX,
    ),
    key: str = Path(
        ...,
        title="Token key",
        example="GpbIL3_qhgZlpfGTFF",
        min_length=22,
        max_length=22,
    ),
    auth_data: TokenData = Depends(authenticate_write),
    context: RequestContext = Depends(context_dependency),
) -> TokenInfo:
    token_service = context.factory.create_token_service()
    update = token_request.dict(exclude_unset=True)
    if "expires" in update and update["expires"] is None:
        update["no_expire"] = True
    info = await token_service.modify_token(
        key,
        auth_data,
        username,
        ip_address=context.request.client.host,
        **update,
    )
    if not info:
        raise NotFoundError("Token not found", ErrorLocation.path, "key")
    return info


@router.get(
    "/users/{username}/tokens/{key}/change-history",
    response_model=List[TokenChangeHistoryEntry],
    response_model_exclude_unset=True,
    responses={404: {"description": "Token not found", "model": ErrorModel}},
    summary="Get change history of token",
    tags=["user"],
)
async def get_token_change_history(
    username: str = Path(
        ...,
        title="Username",
        example="someuser",
        min_length=1,
        max_length=64,
        regex=USERNAME_REGEX,
    ),
    key: str = Path(
        ...,
        title="Token key",
        example="GpbIL3_qhgZlpfGTFF",
        min_length=22,
        max_length=22,
    ),
    auth_data: TokenData = Depends(authenticate_read),
    context: RequestContext = Depends(context_dependency),
) -> List[Dict[str, Any]]:
    token_service = context.factory.create_token_service()
    results = token_service.get_change_history(
        auth_data, username=username, key=key
    )
    if not results.entries:
        raise NotFoundError("Token not found", ErrorLocation.path, "key")
    return [r.reduced_dict() for r in results.entries]
