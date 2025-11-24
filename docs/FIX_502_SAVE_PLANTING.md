# Fix: 502 Bad Gateway on /save_planting/

## Problem

Getting `502 Bad Gateway` when accessing `https://3.235.196.246.nip.io/save_planting/`

This means Nginx is running but can't connect to your Django/Gunicorn backend.

## Quick Diagnosis

### Step 1: Check if Service is Running

```bash
sudo systemctl status smartharvester
```

**If not running:**
```bash
sudo systemctl start smartharvester
sudo systemctl enable smartharvester
```

### Step 2: Check if Backend is Listening

```bash
# Check if port 8000 is listening
sudo netstat -tlnp | grep 8000
# Or
sudo ss -tlnp | grep 8000
```

**Expected:** Should show Gunicorn listening on port 8000

### Step 3: Test Backend Directly

```bash
# Test if backend responds
curl -I http://127.0.0.1:8000/

# Test save_planting endpoint
curl -I http://127.0.0.1:8000/save_planting/
```

**If these fail:** Backend is down or crashed

### Step 4: Check Service Logs

```bash
# Check recent errors
sudo journalctl -u smartharvester -n 100 --no-pager | grep -i "error\|exception\|traceback"

# Watch logs in real-time
sudo journalctl -u smartharvester -f
```

### Step 5: Check Nginx Error Logs

```bash
# Check nginx errors
sudo tail -50 /var/log/nginx/error.log | grep -i "502\|save_planting\|upstream"
```

## Common Causes & Fixes

### Cause 1: Service Crashed

**Symptoms:**
- `systemctl status smartharvester` shows "failed" or "inactive"
- No process listening on port 8000

**Fix:**
```bash
# Restart service
sudo systemctl restart smartharvester

# Check status
sudo systemctl status smartharvester

# Check logs for crash reason
sudo journalctl -u smartharvester -n 100
```

### Cause 2: Unhandled Exception in View

**Symptoms:**
- Service is running but crashes on specific request
- Logs show Python traceback

**Fix:**
- Check logs for the exact error
- The view has been updated with better error handling
- Ensure all required fields are present in POST request

### Cause 3: Nginx Can't Connect

**Symptoms:**
- Backend responds to `curl http://127.0.0.1:8000/` but Nginx returns 502
- Nginx error log shows "connect() failed"

**Fix:**
```bash
# Check nginx config
sudo nginx -t

# Verify proxy_pass points to correct port
sudo grep -A 5 "location /" /etc/nginx/sites-enabled/default

# Should show:
# proxy_pass http://127.0.0.1:8000;

# Reload nginx
sudo systemctl reload nginx
```

### Cause 4: Timeout

**Symptoms:**
- Request takes too long
- Nginx error log shows "upstream timed out"

**Fix:**
Add timeout settings to nginx config:
```nginx
proxy_connect_timeout 60s;
proxy_send_timeout 60s;
proxy_read_timeout 60s;
```

## Step-by-Step Fix

### 1. Verify Service Status

```bash
sudo systemctl status smartharvester
```

If not running:
```bash
sudo systemctl start smartharvester
```

### 2. Check Backend is Accessible

```bash
# Test backend
curl http://127.0.0.1:8000/

# Should return HTML, not 502
```

### 3. Check Logs for Errors

```bash
# Service logs
sudo journalctl -u smartharvester -n 100 | tail -50

# Nginx logs
sudo tail -50 /var/log/nginx/error.log
```

### 4. Test save_planting Endpoint

```bash
# Test GET (should redirect)
curl -I http://127.0.0.1:8000/save_planting/

# Test POST (requires authentication)
curl -X POST http://127.0.0.1:8000/save_planting/ \
  -H "Cookie: sessionid=..." \
  -d "crop_name=test&planting_date=2025-01-01"
```

### 5. Restart Services

```bash
# Restart Django service
sudo systemctl restart smartharvester

# Reload Nginx
sudo systemctl reload nginx
```

## Important Notes

### About /save_planting/ Endpoint

- **Method:** POST only
- **GET requests:** Redirects to index (should not cause 502)
- **POST requests:** Requires authentication and form data

### If Accessing via Browser

The endpoint should only be accessed via form submission, not directly in browser.

If you're seeing 502 when accessing directly:
1. This is expected - it's a POST endpoint
2. Use the "Add New Planting" form instead
3. The form should POST to `/save_planting/`

### Error Handling Improvements

The view has been updated to:
- Return proper HTTP error responses instead of redirects
- Handle date parsing errors gracefully
- Handle plan calculation errors gracefully
- Log all errors for debugging

## Quick Test Script

Run the diagnostic script:
```bash
chmod +x scripts/diagnose_save_planting_502.sh
./scripts/diagnose_save_planting_502.sh
```

This will check:
- Service status
- Port listening
- Backend connectivity
- Recent errors
- Nginx configuration

## Expected Behavior

### GET Request to /save_planting/
- Should redirect to index (302)
- Should NOT return 502

### POST Request to /save_planting/
- Requires authentication
- Requires form data (crop_name, planting_date)
- Should save planting and redirect to index
- Should NOT return 502

If you're getting 502, it means:
1. Backend service is down → Restart service
2. Backend crashed → Check logs
3. Nginx can't connect → Check nginx config
4. Timeout → Increase nginx timeouts

