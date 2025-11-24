# Environment Setup Guide

This guide explains how to configure environment variables for the SmartHarvester application.

## Required Environment Variables

The following environment variables are **required** for Cognito authentication to work:

- `COGNITO_DOMAIN` - Your Cognito domain (e.g., `your-domain.auth.us-east-1.amazoncognito.com`)
- `COGNITO_CLIENT_ID` - Your Cognito App Client ID
- `COGNITO_REDIRECT_URI` - The callback URL (must match Cognito app client settings)
- `COGNITO_CLIENT_SECRET` - Optional, only if your app client has a secret

## Setup for systemd Service

1. Create the environment file directory:
   ```bash
   sudo mkdir -p /etc/systemd/system/smartharvester.service.d
   ```

2. Create the environment file:
   ```bash
   sudo nano /etc/systemd/system/smartharvester.service.d/env.conf
   ```

3. Add your environment variables (see `docs/systemd-service-env.conf.example` for template):
   ```ini
   COGNITO_DOMAIN=your-domain.auth.us-east-1.amazoncognito.com
   COGNITO_CLIENT_ID=your-client-id
   COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/
   COGNITO_CLIENT_SECRET=your-secret-if-applicable
   AWS_REGION=us-east-1
   # ... other vars
   ```

4. Ensure your systemd service unit file includes:
   ```ini
   EnvironmentFile=/etc/systemd/system/smartharvester.service.d/env.conf
   ```

5. Reload and restart:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart smartharvester
   ```

## Setup for Local Development

1. Create a `.env` file in the project root:
   ```bash
   cp docs/systemd-service-env.conf.example .env
   ```

2. Edit `.env` with your actual values (DO NOT commit this file to git)

3. The app will automatically load these via `python-dotenv`

## Validation

After setup, verify the configuration:

```bash
# Check systemd service environment
sudo systemctl show smartharvester --property=Environment

# Check service logs for errors
sudo journalctl -u smartharvester -f

# Test Cognito login endpoint
curl -I https://3.235.196.246.nip.io/auth/login/
```

## Troubleshooting

- **COGNITO_DOMAIN errors**: Ensure the domain is correct and accessible
- **Token exchange failures**: Verify `COGNITO_REDIRECT_URI` matches exactly what's configured in Cognito
- **Database errors**: The app will fall back to sqlite if `DATABASE_NAME` is not set
- **Name resolution errors**: Check that `COGNITO_DOMAIN` is a valid domain

