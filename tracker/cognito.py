import time
import requests
from jose import jwt
from jose.utils import base64url_decode

from django.conf import settings

JWKS_CACHE = {'keys': None, 'fetched_at': 0}
JWKS_TTL = 60 * 60  # 1 hour


def _fetch_jwks():
    now = time.time()
    if JWKS_CACHE['keys'] and now - JWKS_CACHE['fetched_at'] < JWKS_TTL:
        return JWKS_CACHE['keys']
    jwks_url = f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com/{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
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


def build_authorize_url(state=None, scope='openid email profile'):
    domain = settings.COGNITO_DOMAIN
    client_id = settings.COGNITO_CLIENT_ID
    redirect_uri = settings.COGNITO_REDIRECT_URI
    base = f"https://{domain}/oauth2/authorize"
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': scope,
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
        from requests.auth import HTTPBasicAuth
        auth = HTTPBasicAuth(settings.COGNITO_CLIENT_ID, settings.COGNITO_CLIENT_SECRET)
        # remove client_id from body when using HTTP Basic
        data.pop('client_id', None)
    r = requests.post(token_url, data=data, headers=headers, auth=auth, timeout=5)
    r.raise_for_status()
    return r.json()
