"""
Lightweight async metrics helpers that write counters and latency samples to Redis.
Provides a small JSON endpoint consumer-friendly format without requiring Prometheus.

Design:
- Counters: Redis INCR on key `metrics:counter:{name}`
- Latency samples: LPUSH to `metrics:lat:{name}`, LTRIM to keep last 1000 samples
- get_metrics() aggregates counters and computes simple stats for lat samples (count, avg, p50)
- If Redis is not available, operations are kept in-memory (process-local) for testing/dev.
"""

from typing import Dict, Any
import statistics

# We'll import redis_client lazily from app to avoid circular import at module import time

_MEM_COUNTERS: Dict[str, int] = {}
_MEM_LATS: Dict[str, list] = {}


async def _get_redis():
    try:
        from city_guides.src.app import redis_client
        return redis_client
    except Exception:
        return None


async def increment(name: str, amount: int = 1) -> None:
    """Increment a named counter by amount"""
    rc = await _get_redis()
    key = f"metrics:counter:{name}"
    if rc:
        try:
            await rc.incrby(key, amount)
        except Exception:
            # best-effort fallback to memory
            _MEM_COUNTERS[name] = _MEM_COUNTERS.get(name, 0) + amount
    else:
        _MEM_COUNTERS[name] = _MEM_COUNTERS.get(name, 0) + amount


async def observe_latency(name: str, ms: float, max_samples: int = 1000) -> None:
    """Record a latency sample (milliseconds) for a named metric"""
    rc = await _get_redis()
    key = f"metrics:lat:{name}"
    if rc:
        try:
            # LPUSH value and LTRIM to keep last max_samples
            await rc.lpush(key, str(ms))
            await rc.ltrim(key, 0, max_samples - 1)
        except Exception:
            _MEM_LATS.setdefault(name, []).insert(0, ms)
            if len(_MEM_LATS[name]) > max_samples:
                _MEM_LATS[name] = _MEM_LATS[name][:max_samples]
    else:
        _MEM_LATS.setdefault(name, []).insert(0, ms)
        if len(_MEM_LATS[name]) > max_samples:
            _MEM_LATS[name] = _MEM_LATS[name][:max_samples]


async def get_metrics() -> Dict[str, Any]:
    """Return a JSON-serializable dict of metrics: counters and simple latency stats

    This function prefers Redis-backed metrics when available, but will also merge
    any in-memory samples collected before Redis became available so tests and
    startup instrumentation are not lost.
    """
    rc = await _get_redis()
    out = {"counters": {}, "latencies": {}}
    if rc:
        try:
            # list all counter keys
            # Note: KEYS is acceptable for small-scale usage; if used in prod with large keyspace, change to SCAN
            keys = await rc.keys('metrics:counter:*')
            for k in keys:
                try:
                    # keys may be bytes
                    key = k.decode() if isinstance(k, (bytes, bytearray)) else k
                    name = key.split(':', 2)[-1]
                    v = await rc.get(key)
                    out['counters'][name] = int(v) if v is not None else 0
                except Exception:
                    continue

            # For latencies we will collect raw lists so we can merge in-memory samples
            raw_lat_vals = {}
            lat_keys = await rc.keys('metrics:lat:*')
            for k in lat_keys:
                try:
                    key = k.decode() if isinstance(k, (bytes, bytearray)) else k
                    name = key.split(':', 2)[-1]
                    vals = await rc.lrange(key, 0, -1)
                    vals = [float(v) for v in vals]
                    raw_lat_vals[name] = vals
                except Exception:
                    continue

            # Merge in-memory counters/samples collected before Redis was available
            for n, v in _MEM_COUNTERS.items():
                out['counters'][n] = out['counters'].get(n, 0) + v

            for n, mem_vals in _MEM_LATS.items():
                combined = list(mem_vals)
                if n in raw_lat_vals:
                    combined = combined + raw_lat_vals.get(n, [])
                if combined:
                    out['latencies'][n] = {
                        'count': len(combined),
                        'avg_ms': sum(combined) / len(combined),
                        'p50_ms': float(statistics.median(combined))
                    }

            # Also include any lat keys that were in Redis but had no in-memory samples
            for n, vals in raw_lat_vals.items():
                if n in out['latencies']:
                    continue
                if vals:
                    out['latencies'][n] = {
                        'count': len(vals),
                        'avg_ms': sum(vals) / len(vals),
                        'p50_ms': float(statistics.median(vals))
                    }

            return out
        except Exception:
            # fallback to mem
            pass

    # In-memory fallback
    for n, v in _MEM_COUNTERS.items():
        out['counters'][n] = v
    for n, vals in _MEM_LATS.items():
        if vals:
            out['latencies'][n] = {
                'count': len(vals),
                'avg_ms': sum(vals) / len(vals),
                'p50_ms': float(statistics.median(vals))
            }
    return out
