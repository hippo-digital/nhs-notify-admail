from fastapi import (
    HTTPException,
    status,
    Request,
)
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.responses import JSONResponse
import logging
import os
import requests
from jose import jwk, jwt
from jose.exceptions import JWTError
from app.core import constants

logger = logging.getLogger(__name__)


class CognitoAuthenticator:
    def __init__(self):
        self.region = os.environ.get("COGNITO_REGION", "eu-west-2")
        self.userpool_id = os.environ.get("COGNITO_USER_POOL_ID")
        self.app_client_id = os.environ.get("COGNITO_APP_CLIENT_ID")

        if not self.userpool_id:
            raise ValueError("COGNITO_USER_POOL_ID environment variable not set")
        if not self.app_client_id:
            logger.warning(
                "COGNITO_APP_CLIENT_ID environment variable not set. Audience validation will be skipped."
            )

        self.issuer = (
            f"https://cognito-idp.{self.region}.amazonaws.com/{self.userpool_id}"
        )
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"
        self._jwks = self._get_jwks()

    def _get_jwks(self):
        try:
            response = requests.get(self.jwks_url)
            response.raise_for_status()
            return response.json()["keys"]
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            return []

    def _find_rsa_key(self, kid):
        for key in self._jwks:
            if key["kid"] == kid:
                return {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
        return None

    def validate_token(self, token: str):
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token header: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        rsa_key = self._find_rsa_key(unverified_header.get("kid"))

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not find a matching public key for token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            decode_kwargs = {
                "algorithms": ["RS256"],
                "issuer": self.issuer,
            }
            if self.app_client_id:
                decode_kwargs["audience"] = self.app_client_id

            payload = jwt.decode(token, rsa_key, **decode_kwargs)
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTClaimsError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid claims: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token validation failed: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred during token validation: {e}",
            )


def _verify_request_token(request: Request, authenticator: CognitoAuthenticator):
    """Helper to extract and validate token from a request."""
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, token = get_authorization_scheme_param(authorization)
    if not token or scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return authenticator.validate_token(token)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, authenticator: CognitoAuthenticator):
        super().__init__(app)
        self.authenticator = authenticator

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in ["/health"]:
            return await call_next(request)

        try:
            payload = _verify_request_token(request, self.authenticator)
            request.state.user = payload
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
                headers=e.headers,
            )

        return await call_next(request)


# This exception handler's purpose is to handle unauthorised 404's, and return them as 401's
# This prevents outside sources from being able to map the API effectively
class NotFoundExceptionHandler:
    def __init__(self, authenticator: CognitoAuthenticator):
        self.authenticator = authenticator

    async def __call__(self, request: Request, exc: HTTPException):
        try:
            _verify_request_token(request, self.authenticator)
            # Valid token, but resource not found
            return JSONResponse(
                status_code=404, content={"detail": constants.ERROR_NOT_FOUND}
            )
        except HTTPException as e:
            # Invalid token
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
                headers=e.headers,
            )
