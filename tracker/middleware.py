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
        # Skip all auth/session checks for auth endpoints to avoid triggering DB access or redirect loops
        # This must be the VERY FIRST check - before any request.user or request.session access
        # This prevents AuthenticationMiddleware from trying to load session from database
        # Also prevents redirect loops when user is on login page without tokens
        if request.path.startswith("/auth/callback/") or request.path.startswith("/auth/login/"):
            logger.debug('CognitoTokenMiddleware: Skipping auth path: %s', request.path)
            # Skip loading user/session completely - return immediately
            return self.get_response(request)
        
        logger.debug('CognitoTokenMiddleware: Processing path: %s', request.path)
        
        # Only verify tokens if they exist - don't require authentication for public pages
        # This allows the home page and other public pages to work without tokens
        try:
            # Check session directly for Cognito tokens (both old and new format)
            # Note: This will trigger session loading, but only for non-callback paths
            id_token = request.session.get('id_token') or request.session.get('cognito_tokens', {}).get('id_token')
            if id_token:
                # Only verify token if it exists - if no token, let the view handle it
                try:
                    # Verify and decode the token to get user payload
                    payload = verify_id_token(id_token)
                    # Attach user payload to request for easy access in views
                    request.cognito_payload = payload
                    request.cognito_user_id = payload.get('sub') or payload.get('username') or payload.get('email')
                    logger.debug('CognitoTokenMiddleware: Token verified successfully for user: %s', request.cognito_user_id)
                except Exception as e:
                    logger.info('ID token verify failed: %s', e)
                    # Try to refresh if refresh_token is available
                    cognito_tokens = request.session.get('cognito_tokens', {})
                    refresh_token = cognito_tokens.get('refresh_token')
                    if refresh_token:
                        try:
                            new = _refresh_with_refresh_token(refresh_token)
                            # Update both old and new session formats
                            request.session['cognito_tokens'] = new
                            request.session['id_token'] = new.get('id_token')
                            request.session['access_token'] = new.get('access_token')
                            # Decode and attach the new token payload
                            if new.get('id_token'):
                                try:
                                    payload = verify_id_token(new.get('id_token'))
                                    request.cognito_payload = payload
                                    request.cognito_user_id = payload.get('sub') or payload.get('username') or payload.get('email')
                                except Exception:
                                    pass
                            logger.info('CognitoTokenMiddleware: Token refreshed successfully')
                        except Exception as refresh_error:
                            logger.warning('Refresh failed: %s; clearing invalid tokens', refresh_error)
                            # Clear invalid tokens from session instead of redirecting
                            # Let the view decide if authentication is required
                            request.session.pop('id_token', None)
                            request.session.pop('access_token', None)
                            request.session.pop('cognito_tokens', None)
                    else:
                        logger.warning('No refresh token available; clearing invalid tokens')
                        # Clear invalid tokens instead of redirecting
                        request.session.pop('id_token', None)
                        request.session.pop('access_token', None)
                        request.session.pop('cognito_tokens', None)
            else:
                logger.debug('CognitoTokenMiddleware: No tokens in session - allowing request to continue')
        except Exception as e:
            # Handle database connection errors gracefully
            # If we can't access the session, just continue to the view
            logger.warning('Middleware session access failed: %s', e)
        
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
