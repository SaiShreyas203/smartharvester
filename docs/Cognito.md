# AWS Cognito Integration (Hosted UI)

This document summarizes how to configure and run the Cognito Hosted UI integration used by this project.

## Required environment variables
- `COGNITO_USER_POOL_ID` (e.g. `us-east-1_HGEM2vRNI`) — set in `config/settings.py` default.
- `COGNITO_CLIENT_ID` — App client ID created in Cognito console.
- `COGNITO_CLIENT_SECRET` — App client secret (if your app client uses a secret).
- `COGNITO_REGION` — AWS region for the user pool (default `us-east-1`).
- `COGNITO_DOMAIN` — Cognito Hosted UI domain (e.g. `your-prefix.auth.us-east-1.amazoncognito.com`).
- `COGNITO_REDIRECT_URI` — Callback URI registered in the App client (default `http://localhost:8000/auth/callback/`).

## Local setup
1. Install new requirements:

```bash
# activate your virtualenv first
pip install -r requirements.txt
```

2. Set environment variables (example for local dev):

```bash
export COGNITO_DOMAIN=my-prefix.auth.us-east-1.amazoncognito.com
export COGNITO_CLIENT_ID=xxxxxxxxxxxx
export COGNITO_CLIENT_SECRET=yyyyyyyyyyyy (if used)
export COGNITO_REDIRECT_URI=http://localhost:8000/auth/callback/
```

3. Ensure your Cognito App client has `Allowed callback URLs` including the redirect used above and `Allowed OAuth Flows` includes `authorization code`.

## How it works in the app
- Visit `/auth/login/` to be redirected to the Cognito Hosted UI.
- After login, Cognito redirects to `/auth/callback/` (handled in `tracker.views.cognito_callback`) which exchanges the authorization code for tokens, verifies the ID token, creates or fetches a Django `User`, and logs them in.
- Tokens are stored in `request.session['cognito_tokens']` for later refresh.
- A middleware `tracker.middleware.CognitoTokenMiddleware` verifies each request's ID token for authenticated users and attempts refresh using `refresh_token` when needed.

## Notes and recommendations
- Use HTTPS and proper secure cookie flags in production.
- Consider storing only necessary token information (avoid storing long-lived secrets in session if not required).
- For production, configure a more robust token caching and JWKS refresh policy.
- Map Cognito groups/claims to Django permissions if needed.

## Troubleshooting
- If login fails, check the App client `Allowed callback URLs` and domain configuration.
- If token verification fails, ensure `COGNITO_CLIENT_ID` and `COGNITO_REGION` are set correctly and JWKS URL is accessible.

