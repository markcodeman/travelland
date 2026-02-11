"""
Async utilities for proper event loop management and async patterns.

This module provides utilities to fix common asyncio issues:
- Multiple event loop creation
- Inconsistent async patterns
- Event loop abuse in tests and providers
"""

import asyncio
import functools
import inspect
from typing import Any, Awaitable, Callable, TypeVar, Union

T = TypeVar('T')

class AsyncRunner:
    """Safe async execution utilities to prevent event loop issues."""
    
    @staticmethod
    def run(coro: Awaitable[T]) -> T:
        """Execute a coroutine safely, using existing event loop if available.
        
        This fixes the common pattern of calling asyncio.run() in multiple places
        which can cause "Cannot run the event loop while another loop is running" errors.
        
        Args:
            coro: Coroutine to execute
            
        Returns:
            Result of the coroutine
            
        Raises:
            RuntimeError: If no event loop is available and cannot create one
        """
        try:
            # Try to use existing running loop
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(coro)
        except RuntimeError:
            # No running loop, create one safely
            return asyncio.run(coro)
    
    @staticmethod
    def ensure_future(coro: Awaitable[T]) -> asyncio.Future:
        """Create a Future for a coroutine, ensuring proper event loop usage.
        
        Args:
            coro: Coroutine to wrap in a Future
            
        Returns:
            Future object
        """
        try:
            loop = asyncio.get_running_loop()
            return asyncio.ensure_future(coro, loop=loop)
        except RuntimeError:
            # No running loop, use default
            return asyncio.ensure_future(coro)

def async_to_sync(func: Callable[..., Awaitable[T]]) -> Callable[..., T]:
    """Decorator to convert async functions to sync functions.
    
    This is useful for:
    - Test functions that need to call async code
    - Legacy sync code that needs to call async providers
    - CLI commands that need async functionality
    
    Example:
        @async_to_sync
        async def get_data():
            return await some_async_operation()
            
        # Can now be called as:
        result = get_data()  # Synchronous call
    
    Args:
        func: Async function to convert
        
    Returns:
        Synchronous wrapper function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        coro = func(*args, **kwargs)
        return AsyncRunner.run(coro)
    
    return wrapper

def sync_to_async(func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    """Decorator to convert sync functions to async functions.
    
    This is useful for:
    - Making sync code work in async contexts
    - Running CPU-bound operations in thread pool
    - Integrating with async frameworks
    
    Example:
        @sync_to_async
        def cpu_bound_operation():
            return expensive_sync_calculation()
            
        # Can now be called as:
        result = await cpu_bound_operation()  # Async call
    
    Args:
        func: Sync function to convert
        
    Returns:
        Async wrapper function
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        loop = asyncio.get_running_loop()
        # Run in thread pool to avoid blocking the event loop
        return await loop.run_in_executor(None, func, *args, **kwargs)
    
    return wrapper

class AsyncContextManager:
    """Context manager for async operations with proper cleanup."""
    
    def __init__(self, async_init_func: Callable[..., Awaitable[Any]]):
        """Initialize with an async initialization function.
        
        Args:
            async_init_func: Async function that returns the resource
        """
        self._async_init = async_init_func
        self._resource = None
    
    async def __aenter__(self) -> Any:
        """Async enter context."""
        self._resource = await self._async_init()
        return self._resource
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async exit context with cleanup."""
        if self._resource:
            # Try to call cleanup methods if they exist
            if hasattr(self._resource, 'close'):
                if inspect.iscoroutinefunction(self._resource.close):
                    await self._resource.close()
                else:
                    self._resource.close()
            elif hasattr(self._resource, 'aclose'):
                if inspect.iscoroutinefunction(self._resource.aclose):
                    await self._resource.aclose()
                else:
                    self._resource.aclose()

def with_timeout(timeout: float = 30.0):
    """Decorator to add timeout to async functions.
    
    Args:
        timeout: Timeout in seconds (default: 30)
        
    Returns:
        Decorated function with timeout
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Operation timed out after {timeout} seconds")
        return wrapper
    return decorator

def retry_async(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """Decorator for retrying async functions on failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay (2.0 = exponential backoff)
        exceptions: Tuple of exception types to catch and retry
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    # Wait before retrying
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            # If we get here, all retries failed
            raise last_exception
        
        return wrapper
    return decorator

def batch_async(
    items: list,
    func: Callable[[Any], Awaitable[Any]],
    concurrency: int = 5,
    timeout: float = 60.0
) -> Callable[..., Awaitable[list]]:
    """Execute async function on multiple items with concurrency control.
    
    Args:
        items: List of items to process
        func: Async function to apply to each item
        concurrency: Maximum number of concurrent operations
        timeout: Timeout for the entire batch operation
        
    Returns:
        List of results in the same order as input items
    """
    async def execute_batch() -> list:
        semaphore = asyncio.Semaphore(concurrency)
        
        async def process_item(item):
            async with semaphore:
                return await func(item)
        
        tasks = [process_item(item) for item in items]
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=timeout
        )
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Log the error but continue processing
                print(f"Error processing item {i}: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        return processed_results
    
    return execute_batch

# Common timeout configurations
TIMEOUTS = {
    'search': 10.0,
    'image': 15.0,
    'geo': 8.0,
    'ai': 30.0,
    'api': 30.0,
    'cache': 5.0
}

def get_timeout(operation: str) -> float:
    """Get timeout for a specific operation.
    
    Args:
        operation: Operation name (search, image, geo, ai, api, cache)
        
    Returns:
        Timeout value in seconds
    """
    return TIMEOUTS.get(operation, 30.0)

# Utility functions for common async patterns

async def gather_with_concurrency(
    n: int, 
    tasks: list[asyncio.Task]
) -> list:
    """Gather async tasks with concurrency limit.
    
    Args:
        n: Maximum number of concurrent tasks
        tasks: List of coroutine functions
        
    Returns:
        List of task results
    """
    semaphore = asyncio.Semaphore(n)
    
    async def sem_task(task):
        async with semaphore:
            return await task
    
    return await asyncio.gather(*[sem_task(task) for task in tasks])

async def wait_for_any(
    tasks: list[asyncio.Task],
    timeout: float = None
) -> tuple[Any, list[asyncio.Task]]:
    """Wait for any task to complete.
    
    Args:
        tasks: List of tasks to wait for
        timeout: Optional timeout
        
    Returns:
        Tuple of (result, remaining_tasks)
    """
    if timeout:
        done, pending = await asyncio.wait(tasks, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
    else:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    
    if done:
        result = done.pop().result()
        return result, list(pending)
    else:
        return None, list(pending)