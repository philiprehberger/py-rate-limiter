# philiprehberger-rate-limiter

[![Tests](https://github.com/philiprehberger/py-rate-limiter/actions/workflows/publish.yml/badge.svg)](https://github.com/philiprehberger/py-rate-limiter/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/philiprehberger-rate-limiter.svg)](https://pypi.org/project/philiprehberger-rate-limiter/)
[![Last updated](https://img.shields.io/github/last-commit/philiprehberger/py-rate-limiter)](https://github.com/philiprehberger/py-rate-limiter/commits/main)

In-memory rate limiter with sliding window and token bucket algorithms.

## Installation

```bash
pip install philiprehberger-rate-limiter
```

## Usage

### Basic Rate Limiting

```python
from philiprehberger_rate_limiter import RateLimiter, Algorithm

limiter = RateLimiter(
    requests=100,
    window_seconds=60,
    algorithm=Algorithm.SLIDING_WINDOW,
)

if limiter.allow("user-123"):
    handle_request()
```

### Check Status

```python
status = limiter.status("user-123")
print(f"Allowed: {status.allowed}")
print(f"Remaining: {status.remaining}/{status.limit}")
print(f"Resets at: {status.reset_at}")
```

### Blocking Wait

```python
# Synchronous — blocks until quota is available or timeout expires
status = limiter.wait("user-123", timeout=5.0)

# Async — awaits until quota is available
status = await limiter.async_acquire("user-123")
```

### Decorator

```python
limiter = RateLimiter(10, 60)

@limiter.limit("10/minute")
def api_endpoint():
    return {"data": "ok"}
```

### Algorithms

```python
# Fixed window — resets at interval boundaries
RateLimiter(100, 60, Algorithm.FIXED_WINDOW)

# Sliding window (default) — rolling time window
RateLimiter(100, 60, Algorithm.SLIDING_WINDOW)

# Token bucket — smooth rate with burst capacity
RateLimiter(100, 60, Algorithm.TOKEN_BUCKET)
```

## API

| Name | Description |
|------|-------------|
| `RateLimiter(requests, window_seconds, algorithm=SLIDING_WINDOW)` | Create a rate limiter |
| `limiter.allow(key)` | Check if request is allowed |
| `limiter.status(key)` | Get detailed `LimitStatus` |
| `limiter.wait(key, timeout=10.0)` | Block until quota available or raise `RateLimitExceeded` |
| `limiter.async_acquire(key)` | Async wait until quota is available |
| `limiter.reset(key)` | Reset state for a key |
| `limiter.reset_all()` | Reset state for all keys |
| `limiter.active_keys()` | List all keys with active state |
| `limiter.limit(rate)` | Decorator with rate string (e.g., `"10/minute"`) |

## Development

```bash
pip install -e .
python -m pytest tests/ -v
```

## Support

If you find this project useful:

⭐ [Star the repo](https://github.com/philiprehberger/py-rate-limiter)

🐛 [Report issues](https://github.com/philiprehberger/py-rate-limiter/issues?q=is%3Aissue+is%3Aopen+label%3Abug)

💡 [Suggest features](https://github.com/philiprehberger/py-rate-limiter/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)

❤️ [Sponsor development](https://github.com/sponsors/philiprehberger)

🌐 [All Open Source Projects](https://philiprehberger.com/open-source-packages)

💻 [GitHub Profile](https://github.com/philiprehberger)

🔗 [LinkedIn Profile](https://www.linkedin.com/in/philiprehberger)

## License

[MIT](LICENSE)
