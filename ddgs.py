# Minimal compatibility shim for ddgs (duckduckgo_search) allowing tests to run
# when the real `ddgs` package is not installed in the environment.
class DDGS:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def text(self, query, **kwargs):
        # Yield no results by default; the real package yields dict-like results
        return iter([])
