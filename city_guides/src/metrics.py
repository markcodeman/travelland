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


# Global in-memory fallback store (used when Redis unavailable)
metrics_store = None


# We'll import redis_client lazily from app to avoid circular import at module import time

class MetricsStore:
    """In-memory fallback for metrics (counters and latencies)."""
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.lats: Dict[str, list] = {}

    def increment(self, name: str, amount: int = 1):
        self.counters[name] = self.counters.get(name, 0) + amount

    def observe_latency(self, name: str, ms: float, max_samples: int = 1000):
        self.lats.setdefault(name, []).insert(0, ms)
        if len(self.lats[name]) > max_samples:
            self.lats[name] = self.lats[name][:max_samples]


# Instantiate global fallback store
metrics_store = MetricsStore()


async def _get_redis():
    try:
        from city_guides.src.app import redis_client
        return redis_client
    except Exception:
        return None


async def increment(name: str, amount: int = 1) -> None:
    """Increment a named counter by amount"""
    """Increment a named counter by amount, using provided MetricsStore for fallback."""
    async def _increment(rc, key):
        try:
            await rc.incrby(key, amount)
        except Exception:
            if metrics_store:
                metrics_store.increment(name, amount)

    key = f"metrics:counter:{name}"
    rc = await _get_redis()
    if rc:
        await _increment(rc, key)
    elif metrics_store:
        metrics_store.increment(name, amount)


async def observe_latency(name: str, ms: float, max_samples: int = 1000) -> None:
    """Record a latency sample (milliseconds) for a named metric"""
    """Record a latency sample (milliseconds) for a named metric, using provided MetricsStore for fallback."""
    async def _observe(rc, key):
        try:
            await rc.lpush(key, str(ms))
            await rc.ltrim(key, 0, max_samples - 1)
        except Exception:
            if metrics_store:
                metrics_store.observe_latency(name, ms, max_samples)

    key = f"metrics:lat:{name}"
    rc = await _get_redis()
    if rc:
        await _observe(rc, key)
    elif metrics_store:
        metrics_store.observe_latency(name, ms, max_samples)


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
            keys = await rc.keys('metrics:counter:*')
            for k in keys:
                try:
                    key = k.decode() if isinstance(k, (bytes, bytearray)) else k
                    name = key.split(':', 2)[-1]
                    v = await rc.get(key)
                    out['counters'][name] = int(v) if v is not None else 0
                except Exception:
                    continue

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

            # Merge in-memory counters/samples from provided metrics_store
            if metrics_store:
                for n, v in metrics_store.counters.items():
                    out['counters'][n] = out['counters'].get(n, 0) + v
                for n, mem_vals in metrics_store.lats.items():
                    combined = list(mem_vals)
                    if n in raw_lat_vals:
                        combined = combined + raw_lat_vals.get(n, [])
                    if combined:
                        out['latencies'][n] = {
                            'count': len(combined),
                            'avg_ms': sum(combined) / len(combined),
                            'p50_ms': float(statistics.median(combined))
                        }

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
            pass

    # In-memory fallback only
    if metrics_store:
        for n, v in metrics_store.counters.items():
            out['counters'][n] = v
        for n, vals in metrics_store.lats.items():
            if vals:
                out['latencies'][n] = {
                    'count': len(vals),
                    'avg_ms': sum(vals) / len(vals),
                    'p50_ms': float(statistics.median(vals))
                }
    return out
