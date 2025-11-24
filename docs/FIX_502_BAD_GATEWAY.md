# Fix: 502 Bad Gateway After Cognito Login

## The Problem

After successful Cognito login, you're redirected to `https://3.235.196.246.nip.io/` but get:
```
502 Bad Gateway
nginx/1.18.0 (Ubuntu)
```

This means nginx is running but can't connect to your Django/Gunicorn backend.

## Quick Diagnosis

### Step 1: Check if Gunicorn/Django is Running

```bash
# Check if the service is running
sudo systemctl status smartharvester

# Check if Gunicorn process is running
ps aux | grep gunicorn

# Check what port it's listening on
sudo netstat -tlnp | grep gunicorn
# Or
sudo ss -tlnp | grep gunicorn
```

**Expected**: Should show Gunicorn listening on port 8000 (or whatever port is configured)

### Step 2: Check Nginx Configuration

```bash
# Check nginx configuration
sudo nginx -t

# View nginx configuration
sudo cat /etc/nginx/sites-available/default
# Or
sudo cat /etc/nginx/sites-enabled/default
```

Look for `proxy_pass` directive - it should point to where Gunicorn is running (usually `http://127.0.0.1:8000` or `http://localhost:8000`)

### Step 3: Check Nginx Error Logs

```bash
# Check nginx error logs
sudo tail -f /var/log/nginx/error.log

# Check access logs
sudo tail -f /var/log/nginx/access.log
```

## Common Causes & Fixes

### Cause 1: Service Not Running

**Check:**
```bash
sudo systemctl status smartharvester
```

**Fix if not running:**
```bash
sudo systemctl start smartharvester
sudo systemctl enable smartharvester  # Enable on boot
```

### Cause 2: Wrong Port in Nginx Config

**Check nginx config:**
```bash
sudo cat /etc/nginx/sites-enabled/default | grep proxy_pass
```

**Should show something like:**
```nginx
proxy_pass http://127.0.0.1:8000;
```

**If wrong, fix it:**
```bash
sudo nano /etc/nginx/sites-enabled/default
```

Update the `proxy_pass` to match where Gunicorn is running (check with `ps aux | grep gunicorn`)

### Cause 3: Gunicorn Not Listening on Expected Interface

**Check what Gunicorn is bound to:**
```bash
sudo netstat -tlnp | grep gunicorn
```

**Should show:**
```
tcp  0  0  127.0.0.1:8000  0.0.0.0:*  LISTEN  <pid>/gunicorn
```

**If Gunicorn is bound to `0.0.0.0:8000` instead of `127.0.0.1:8000`, that's fine too.**

**Check your service unit file:**
```bash
sudo cat /etc/systemd/system/smartharvester.service | grep ExecStart
```

Should show Gunicorn binding to `0.0.0.0:8000` or `127.0.0.1:8000`

### Cause 4: Firewall Blocking Connection

**Check if port 8000 is accessible locally:**
```bash
curl http://127.0.0.1:8000/
```

**If this works, nginx should be able to connect. If not, check firewall:**
```bash
sudo ufw status
```

### Cause 5: Nginx Configuration Error

**Test nginx configuration:**
```bash
sudo nginx -t
```

**If errors, fix them, then reload:**
```bash
sudo systemctl reload nginx
```

## Recommended Nginx Configuration

Here's a basic nginx configuration that should work:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name 3.235.196.246.nip.io;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name 3.235.196.246.nip.io;

    # SSL configuration (if you have certificates)
    # ssl_certificate /path/to/cert.pem;
    # ssl_certificate_key /path/to/key.pem;

    # For development without SSL, you might use port 80 instead

    # Logging
    access_log /var/log/nginx/smartharvester_access.log;
    error_log /var/log/nginx/smartharvester_error.log;

    # Maximum upload size
    client_max_body_size 10M;

    # Proxy settings
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files (if serving via nginx)
    location /static/ {
        alias /path/to/your/project/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files (if serving via nginx)
    location /media/ {
        alias /path/to/your/project/media/;
        expires 30d;
    }
}
```

## Step-by-Step Fix

### Step 1: Verify Service is Running

```bash
sudo systemctl status smartharvester
```

If not running:
```bash
sudo systemctl start smartharvester
```

### Step 2: Check What Port Gunicorn is Using

```bash
sudo netstat -tlnp | grep gunicorn
```

Note the port (usually 8000)

### Step 3: Test Backend Directly

```bash
# Test if backend responds
curl http://127.0.0.1:8000/

# Should return HTML, not 502
```

### Step 4: Check Nginx Config Points to Correct Port

```bash
sudo cat /etc/nginx/sites-enabled/default | grep -A 5 "location /"
```

Should show `proxy_pass http://127.0.0.1:8000;` (or whatever port Gunicorn is on)

### Step 5: Update Nginx Config if Needed

```bash
sudo nano /etc/nginx/sites-enabled/default
```

Ensure `proxy_pass` matches Gunicorn's port

### Step 6: Test and Reload Nginx

```bash
# Test configuration
sudo nginx -t

# If OK, reload
sudo systemctl reload nginx
```

### Step 7: Check Logs

```bash
# Nginx error log
sudo tail -f /var/log/nginx/error.log

# Service logs
sudo journalctl -u smartharvester -f
```

## Quick Test Commands

```bash
# 1. Is service running?
sudo systemctl is-active smartharvester

# 2. Is Gunicorn listening?
sudo netstat -tlnp | grep 8000

# 3. Can nginx reach backend?
curl http://127.0.0.1:8000/

# 4. Test nginx config
sudo nginx -t

# 5. Check nginx status
sudo systemctl status nginx
```

## Still Getting 502?

1. **Check service logs for errors:**
   ```bash
   sudo journalctl -u smartharvester -n 50
   ```

2. **Check if port conflict:**
   ```bash
   sudo lsof -i :8000
   ```

3. **Restart both services:**
   ```bash
   sudo systemctl restart smartharvester
   sudo systemctl restart nginx
   ```

4. **Check SELinux (if enabled):**
   ```bash
   getenforce
   # If Enforcing, might need to allow nginx to connect
   ```

## Expected Working State

✅ Service running: `sudo systemctl status smartharvester` shows "active (running)"  
✅ Gunicorn listening: `netstat -tlnp | grep 8000` shows process  
✅ Backend responds: `curl http://127.0.0.1:8000/` returns HTML  
✅ Nginx configured: `proxy_pass http://127.0.0.1:8000;` in config  
✅ Nginx running: `sudo systemctl status nginx` shows "active (running)"

