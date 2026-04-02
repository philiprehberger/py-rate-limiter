# philiprehberger-rate-limiter

[![Tests](https://github.com/philiprehberger/py-rate-limiter/actions/workflows/publish.yml/badge.svg)](https://github.com/philiprehberger/py-rate-limiter/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/philiprehberger-rate-limiter.svg)](https://pypi.org/project/philiprehberger-rate-limiter/)
[![Last updated](https://img.shields.io/github/last-commit/philiprehberger/py-rate-limiter)](https://github.com/philiprehberger/py-rate-limiter/commits/main)

In-memory rate limiter with sliding window, token bucket, and leaky bucket algorithms.

## Installation

```bash
pip install philiprehberger-rate-limiter
```

## Usage

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
from philiprehberger_rate_limiter import RateLimiter

limiter = RateLimiter(100, 60)
status = limiter.status("user-123")
print(f"Allowed: {status.allowed}")
print(f"Remaining: {status.remaining}/{status.limit}")
print(f"Resets at: {status.reset_at}")
```

### Usage Statistics

```python
from philiprehberger_rate_limiter import RateLimiter

limiter = RateLimiter(100, 60)
limiter.allow("user-123")

stats = limiter.get_stats("user-123")
print(f"Current usage: {stats.current_usage}")
print(f"Remaining: {stats.remaining}")
print(f"Reset at: {stats.reset_at}")
```

### Blocking Wait

```python
from philiprehberger_rate_limiter import RateLimiter

limiter = RateLimiter(100, 60)

# Synchronous — blocks until quota is available or timeout expires
status = limiter.wait("user-123", timeout=5.0)

# Async — awaits until quota is available
status = await limiter.async_acquire("user-123")
```

### Async Context Manager

```python
from philiprehberger_rate_limiter import RateLimiter

limiter = RateLimiter(100, 60)

async with limiter:
    status = await limiter.async_acquire("user-123")
    if status.allowed:
        await handle_request()
```

### Decorator

```python
from philiprehberger_rate_limiter import RateLimiter, rate_limit

# Standalone decorator
@rate_limit(calls=10, period=60)
def api_endpoint():
    return {"data": "ok"}

# Instance-based decorator
limiter = RateLimiter(10, 60)

@limiter.limit("10/minute")
def another_endpoint():
    return {"data": "ok"}

# Async function decorator
@rate_limit(calls=10, period=60)
async def async_endpoint():
    return {"data": "ok"}
```

### Rate Limiter Groups

```python
from philiprehberger_rate_limiter import RateLimiter, RateLimiterGroup

limiter = RateLimiter(100, 60)
group = RateLimiterGroup(limiter, ["api-key-1", "api-key-2", "api-key-3"])

# All keys in the group share one rate limit pool
group.allow("api-key-1")  # consumes from shared pool
group.allow("api-key-2")  # consumes from same pool

stats = group.get_stats()
print(f"Group usage: {stats.current_usage}/{stats.limit}")
```

### Algorithms

```python
from philiprehberger_rate_limiter import RateLimiter, Algorithm

# Fixed window — resets at interval boundaries
RateLimiter(100, 60, Algorithm.FIXED_WINDOW)

# Sliding window (default) — rolling time window
RateLimiter(100, 60, Algorithm.SLIDING_WINDOW)

# Token bucket — smooth rate with burst capacity
RateLimiter(100, 60, Algorithm.TOKEN_BUCKET)

# Leaky bucket — constant drain rate, smooths bursts
RateLimiter(100, 60, Algorithm.LEAKY_BUCKET)
```

## API

| Function / Class | Description |
|------------------|-------------|
| `RateLimiter(requests, window_seconds, algorithm)` | Create a rate limiter |
| `limiter.allow(key)` | Check if request is allowed |
| `limiter.status(key)` | Get detailed `LimitStatus` |
| `limiter.get_stats(key)` | Get `RateLimiterStats` without consuming a request |
| `limiter.wait(key, timeout)` | Block until quota available or raise `RateLimitExceeded` |
| `limiter.async_acquire(key)` | Async wait until quota is available |
| `limiter.reset(key)` | Reset state for a key |
| `limiter.reset_all()` | Reset state for all keys |
| `limiter.active_keys()` | List all keys with active state |
| `limiter.limit(rate)` | Decorator with rate string (e.g., `"10/minute"`) |
| `RateLimiterGroup(limiter, keys)` | Create a shared rate limit group |
| `group.allow(key)` | Check if request is allowed against shared pool |
| `group.status(key)` | Get shared `LimitStatus` |
| `group.get_stats()` | Get shared `RateLimiterStats` |
| `group.reset()` | Reset shared group state |
| `rate_limit(calls, period, algorithm)` | Standalone decorator for rate limiting |
| `Algorithm` | Enum: `FIXED_WINDOW`, `SLIDING_WINDOW`, `TOKEN_BUCKET`, `LEAKY_BUCKET` |
| `LimitStatus` | Dataclass: `allowed`, `remaining`, `reset_at`, `limit` |
| `RateLimiterStats` | Dataclass: `current_usage`, `remaining`, `reset_at`, `limit` |
| `RateLimitExceeded` | Exception raised when rate limit is exceeded |

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
