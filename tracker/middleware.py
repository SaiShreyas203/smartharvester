import time
import logging
from django.conf import settings
from django.shortcuts import redirect
from .cognito import verify_id_token, exchange_code_for_tokens
from .cognito import validate_cognito_token

logger = logging.getLogger(__name__)


class CognitoTokenMiddleware:
    """Middleware that ensures a valid Cognito ID token is present in session.

    Behavior:
    - If `request.session['cognito_tokens']` contains an `id_token`, verify it.
    - If verification fails and a `refresh_token` is present, attempt to refresh tokens.
    - If refresh fails, redirect user to the Cognito Hosted UI login.

    Note: This middleware is conservative and only runs for authenticated users.
    It can be adapted to be more permissive or to verify on every request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only enforce for logged-in users (who previously completed Cognito flow)
        if request.user.is_authenticated:
            toks = request.session.get('cognito_tokens')
            if toks:
                id_token = toks.get('id_token')
                if id_token:
                    try:
                        verify_id_token(id_token)
                    except Exception as e:
                        logger.info('ID token verify failed: %s', e)
                        # try to refresh
                        refresh_token = toks.get('refresh_token')
                        if refresh_token:
                            try:
                                new = _refresh_with_refresh_token(refresh_token)
                                request.session['cognito_tokens'] = new
                            except Exception:
                                logger.info('Refresh failed; redirecting to login')
                                return redirect('cognito_login')
                        else:
                            return redirect('cognito_login')
        response = self.get_response(request)
        return response


def _refresh_with_refresh_token(refresh_token):
    # Exchange refresh token for new tokens using token endpoint
    domain = settings.COGNITO_DOMAIN
    token_url = f"https://{domain}/oauth2/token"
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': settings.COGNITO_CLIENT_ID,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    auth = None
    if settings.COGNITO_CLIENT_SECRET:
        from requests.auth import HTTPBasicAuth
        auth = HTTPBasicAuth(settings.COGNITO_CLIENT_ID, settings.COGNITO_CLIENT_SECRET)
        data.pop('client_id', None)
    import requests
    r = requests.post(token_url, data=data, headers=headers, auth=auth, timeout=5)
    r.raise_for_status()
    return r.json()
