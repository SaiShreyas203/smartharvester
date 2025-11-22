import time
from jose import jwt
from jose.utils import base64url_decode

from django.conf import settings

JWKS_CACHE = {'keys': None, 'fetched_at': 0}
JWKS_TTL = 60 * 60  # 1 hour

import boto3
import jwt
from jwt.algorithms import RSAAlgorithm

COGNITO_REGION = "eu-west-1"
USER_POOL_ID = "your-userpool-id"
APP_CLIENT_ID = "your-app-client-id"


def _fetch_jwks():
    now = time.time()
    if JWKS_CACHE['keys'] and now - JWKS_CACHE['fetched_at'] < JWKS_TTL:
        return JWKS_CACHE['keys']
    jwks_url = f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com/{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    # import requests lazily so missing deps won't crash Django at import time
    import requests
    r = requests.get(jwks_url, timeout=5)
    r.raise_for_status()
    jwks_data = r.json()
    JWKS_CACHE['keys'] = jwks_data.get('keys', [])
    JWKS_CACHE['fetched_at'] = now
    return JWKS_CACHE['keys']


def verify_id_token(id_token, audience=None):
    """Verify Cognito ID token and return payload or raise an exception."""
    if audience is None:
        audience = settings.COGNITO_CLIENT_ID
    jwks = _fetch_jwks()
    # jose.jwt.decode will handle key selection with provided jwks
    payload = jwt.decode(id_token, jwks, algorithms=['RS256'], audience=audience)
    return payload


def build_authorize_url(state=None, scope=None):
    """
    Build Cognito OAuth2 authorization URL.
    If scope is not provided, uses COGNITO_SCOPE from settings (default: 'openid email').
    Ensure the scopes match what's enabled in your Cognito app client settings.
    """
    domain = settings.COGNITO_DOMAIN
    client_id = settings.COGNITO_CLIENT_ID
    redirect_uri = settings.COGNITO_REDIRECT_URI
    # Use scope from parameter, settings, or default
    if scope is None:
        scope = getattr(settings, 'COGNITO_SCOPE', 'openid email')
    base = f"https://{domain}/oauth2/authorize"
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': scope,  # Space-separated is correct for OAuth2
    }
    if state:
        params['state'] = state
    # build query
    from urllib.parse import urlencode
    return base + '?' + urlencode(params)


def exchange_code_for_tokens(code):
    domain = settings.COGNITO_DOMAIN
    token_url = f"https://{domain}/oauth2/token"
    data = {
        'grant_type': 'authorization_code',
        'client_id': settings.COGNITO_CLIENT_ID,
        'code': code,
        'redirect_uri': settings.COGNITO_REDIRECT_URI,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    auth = None
    # If client secret is configured, use HTTP Basic auth as per OAuth2
    if settings.COGNITO_CLIENT_SECRET:
        # HTTPBasicAuth is provided by requests; import lazily
        from requests.auth import HTTPBasicAuth
        auth = HTTPBasicAuth(settings.COGNITO_CLIENT_ID, settings.COGNITO_CLIENT_SECRET)
        # remove client_id from body when using HTTP Basic
        data.pop('client_id', None)
    import requests
    r = requests.post(token_url, data=data, headers=headers, auth=auth, timeout=5)
    r.raise_for_status()
    return r.json()

def validate_cognito_token(id_token):
    try:
        # decode header
        headers = jwt.get_unverified_header(id_token)

        # get JWKS
        jwks_url = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
        jwks = boto3.client("cognito-idp").get_jwks_uri(UserPoolId=USER_POOL_ID)

        # fetch public key
        public_key = RSAAlgorithm.from_jwk(jwks[headers["kid"]])

        decoded = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=APP_CLIENT_ID
        )

        return decoded
    
    except Exception as e:
        print("Token validation error:", e)
        return None