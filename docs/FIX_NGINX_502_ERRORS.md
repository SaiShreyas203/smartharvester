# Fix: Nginx 502 Errors - Connection Refused & Too Big Header

## The Problems

From your nginx error log, there are two issues:

1. **"connect() failed (111: Unknown error)"** - Gunicorn is not running or not accessible
2. **"upstream sent too big header"** - Response headers are too large (likely from large session cookies)

## Fix 1: Ensure Service is Running

### Check if service is running:
```bash
sudo systemctl status smartharvester
```

### If not running, start it:
```bash
sudo systemctl start smartharvester
sudo systemctl enable smartharvester
```

### Verify Gunicorn is listening:
```bash
sudo netstat -tlnp | grep 8000
# Or
sudo ss -tlnp | grep 8000
```

### Test backend directly:
```bash
curl http://127.0.0.1:8000/
```

If this fails, the service isn't running properly. Check logs:
```bash
sudo journalctl -u smartharvester -n 50
```

## Fix 2: Increase Nginx Buffer Sizes

The "upstream sent too big header" error means nginx's default buffer sizes are too small for your response headers (likely due to large Cognito session cookies).

### Update nginx configuration:

```bash
sudo nano /etc/nginx/sites-enabled/default
```

Add these directives in your `server` block (or in the `location /` block):

```nginx
server {
    # ... existing config ...
    
    # Increase buffer sizes for large headers (Cognito tokens in cookies)
    proxy_buffer_size 16k;
    proxy_buffers 8 16k;
    proxy_busy_buffers_size 32k;
    large_client_header_buffers 4 32k;
    
    # Increase header buffer size
    client_header_buffer_size 4k;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Additional buffer settings for this location
        proxy_buffer_size 16k;
        proxy_buffers 8 16k;
        proxy_busy_buffers_size 32k;
    }
}
```

### Or add to http block (affects all sites):

```bash
sudo nano /etc/nginx/nginx.conf
```

Add in the `http` block:

```nginx
http {
    # ... existing config ...
    
    # Increase buffer sizes for large headers
    proxy_buffer_size 16k;
    proxy_buffers 8 16k;
    proxy_busy_buffers_size 32k;
    large_client_header_buffers 4 32k;
    client_header_buffer_size 4k;
}
```

### Test and reload:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Complete Nginx Configuration Example

Here's a complete configuration that addresses both issues:

```nginx
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name 3.235.196.246.nip.io;

    # SSL configuration (if you have certificates)
    # ssl_certificate /path/to/cert.pem;
    # ssl_certificate_key /path/to/key.pem;

    # Increase buffer sizes for large headers (Cognito tokens)
    proxy_buffer_size 16k;
    proxy_buffers 8 16k;
    proxy_busy_buffers_size 32k;
    large_client_header_buffers 4 32k;
    client_header_buffer_size 4k;

    # Logging
    access_log /var/log/nginx/smartharvester_access.log;
    error_log /var/log/nginx/smartharvester_error.log;

    # Maximum upload size
    client_max_body_size 10M;

    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_redirect off;
        
        # Buffer settings
        proxy_buffer_size 16k;
        proxy_buffers 8 16k;
        proxy_busy_buffers_size 32k;
    }

    # Static files
    location /static/ {
        alias /home/ubuntu/myproject/smartharvester/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /home/ubuntu/myproject/smartharvester/media/;
        expires 30d;
    }
}
```

## Step-by-Step Fix

### Step 1: Check Service Status
```bash
sudo systemctl status smartharvester
```

If not running:
```bash
sudo systemctl start smartharvester
sudo systemctl enable smartharvester
```

### Step 2: Verify Backend is Accessible
```bash
# Check if port 8000 is listening
sudo netstat -tlnp | grep 8000

# Test backend
curl http://127.0.0.1:8000/
```

### Step 3: Update Nginx Configuration
```bash
sudo nano /etc/nginx/sites-enabled/default
```

Add the buffer size directives (see above).

### Step 4: Test and Reload
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Step 5: Monitor Logs
```bash
# Watch nginx errors
sudo tail -f /var/log/nginx/error.log

# Watch service logs
sudo journalctl -u smartharvester -f
```

## Why This Happens

1. **Connection Refused (111)**: 
   - Service crashed or stopped
   - Service failed to start due to configuration error
   - Port conflict

2. **Too Big Header**:
   - Cognito tokens stored in cookies can be large
   - Session data in cookies
   - Default nginx buffer (4k-8k) is too small
   - Need to increase to 16k-32k

## Verify the Fix

After applying fixes:

1. **Service should be running:**
   ```bash
   sudo systemctl status smartharvester
   ```

2. **Backend should respond:**
   ```bash
   curl http://127.0.0.1:8000/
   ```

3. **Nginx should connect:**
   ```bash
   curl https://3.235.196.246.nip.io/
   ```

4. **No more errors in log:**
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

## If Service Keeps Crashing

If the service keeps stopping, check:

```bash
# Check service logs for errors
sudo journalctl -u smartharvester -n 100

# Check for Python/Django errors
sudo journalctl -u smartharvester | grep -i "error\|exception\|traceback"

# Check system resources
free -h
df -h
```

Common causes:
- Out of memory
- Database connection errors
- Missing environment variables
- Python import errors

