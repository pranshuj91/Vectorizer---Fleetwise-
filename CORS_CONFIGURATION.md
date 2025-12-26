# CORS Configuration Guide

## ✅ Current Configuration

CORS (Cross-Origin Resource Sharing) is now configured to **allow requests from all origins**.

### Configuration Details

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)
```

### What This Means

- ✅ **All domains** can make requests to your API
- ✅ **All HTTP methods** are allowed (GET, POST, PUT, DELETE, etc.)
- ✅ **All headers** are allowed
- ✅ **Credentials** (cookies, auth headers) are allowed

## 🔒 Production Security Recommendation

For **production environments**, it's recommended to restrict origins to specific domains:

```python
# Production example - restrict to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",
        "https://www.yourdomain.com",
        "https://app.yourdomain.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
```

### Environment-Based Configuration

You can make it configurable via environment variables:

```python
import os

# Get allowed origins from environment, default to all
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then in `.env`:
```env
# For development (allow all)
ALLOWED_ORIGINS=*

# For production (specific domains)
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

## 🧪 Testing CORS

### Test from Browser Console

```javascript
// Test CORS from any domain
fetch('https://your-domain.com/upload', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ test: 'data' })
})
.then(response => response.json())
.then(data => console.log('CORS working!', data))
.catch(error => console.error('CORS error:', error));
```

### Test with cURL

```bash
# Check OPTIONS preflight request
curl -X OPTIONS "https://your-domain.com/upload" \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -v
```

Expected response headers:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: *
Access-Control-Allow-Headers: *
Access-Control-Allow-Credentials: true
```

## 📝 Common CORS Issues

### Issue 1: Preflight Request Failing

**Symptom**: Browser shows CORS error for POST/PUT requests

**Solution**: Ensure `OPTIONS` method is allowed (already included with `allow_methods=["*"]`)

### Issue 2: Credentials Not Working

**Symptom**: Cookies/auth headers not sent

**Solution**: Already configured with `allow_credentials=True`

### Issue 3: Specific Headers Blocked

**Symptom**: Custom headers rejected

**Solution**: Already configured with `allow_headers=["*"]`

## ✅ Current Status

**CORS is fully configured and allows requests from everywhere.**

Your API can now be accessed from:
- ✅ Web browsers (any domain)
- ✅ Mobile apps
- ✅ Other APIs
- ✅ Postman/Insomnia
- ✅ cURL scripts
- ✅ Any client application

---

**Note**: The current configuration is permissive for maximum compatibility. For production, consider restricting origins based on your security requirements.

