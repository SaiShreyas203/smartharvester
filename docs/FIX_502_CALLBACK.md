# Fix: 502 Bad Gateway on Cognito Callback

## Problem
Getting `502 Bad Gateway` when accessing `/auth/callback/` after Cognito login.

## Likely Causes

### 1. Missing Dependencies (Most Likely)
The new JWT verification code requires `cachetools` and `PyJWT`.

**Fix:**
```bash
# On your server, activate virtualenv (if using one)
cd /path/to/your/project
source venv/bin/activate  # or your venv path

# Install missing packages
pip install cachetools PyJWT>=2.0.0

# Or install from requirements
pip install -r requirements.txt
```

### 2. Service Needs Restart
After installing dependencies, restart the Django service:

```bash
sudo systemctl restart smartharvester
sudo systemctl status smartharvester
```

### 3. Check Service Logs
```bash
# Check for import errors or crashes
sudo journalctl -u smartharvester -n 100 | grep -i "error\|import\|module"

# Watch logs in real-time
sudo journalctl -u smartharvester -f
```

## Quick Diagnostic Steps

1. **Check if service is running:**
   ```bash
   sudo systemctl status smartharvester
   ```

2. **Check if dependencies are installed:**
   ```bash
   python3 -c "import cachetools; import jwt; print('Dependencies OK')"
   ```

3. **Test backend directly:**
   ```bash
   curl http://127.0.0.1:8000/auth/callback/
   ```

4. **Check Nginx error log:**
   ```bash
   sudo tail -20 /var/log/nginx/error.log
   ```

## Solution Steps

1. **SSH into your server**
2. **Navigate to project directory**
3. **Install dependencies:**
   ```bash
   pip install cachetools PyJWT>=2.0.0
   ```
4. **Restart service:**
   ```bash
   sudo systemctl restart smartharvester
   ```
5. **Test the callback URL again**

The middleware has been updated to gracefully handle missing dependencies, but you still need to install them for token verification to work.

