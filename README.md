# philiprehberger-rate-limiter

[![Tests](https://github.com/philiprehberger/py-rate-limiter/actions/workflows/publish.yml/badge.svg)](https://github.com/philiprehberger/py-rate-limiter/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/philiprehberger-rate-limiter.svg)](https://pypi.org/project/philiprehberger-rate-limiter/)
[![License](https://img.shields.io/github/license/philiprehberger/py-rate-limiter)](LICENSE)

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

- `RateLimiter(requests, window_seconds, algorithm=SLIDING_WINDOW)` — Create a rate limiter
- `limiter.allow(key)` — Check if request is allowed
- `limiter.status(key)` — Get detailed `LimitStatus`
- `limiter.reset(key)` — Reset state for a key
- `limiter.reset_all()` — Reset state for all keys
- `limiter.active_keys()` — List all keys with active state
- `limiter.limit(rate)` — Decorator with rate string (e.g., `"10/minute"`)

## License

MIT
