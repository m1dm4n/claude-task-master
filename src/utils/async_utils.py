import asyncio
import threading
from typing import Callable, Any, TypeVar, Coroutine

R = TypeVar('R')

def run_async_in_thread(coro: Coroutine[Any, Any, R]) -> R:
    """
    Runs an async coroutine in a new event loop on a separate thread.
    This is useful when you need to call async code from synchronous code
    and an event loop might already be running in the main thread.
    """
    result = []
    exception = []

    def run_in_loop():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(coro)
            result.append(res)
        except Exception as e:
            exception.append(e)
        finally:
            loop.close()

    thread = threading.Thread(target=run_in_loop)
    thread.start()
    thread.join()

    if exception:
        raise exception[0]
    return result[0]

def run_async_tasks_sync(coro: Coroutine[Any, Any, R]) -> R:
    """
    Executes an async coroutine. If an event loop is already running,
    it runs the coroutine in a new thread. Otherwise, it uses asyncio.run().
    """
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            return run_async_in_thread(coro)
        else:
            return asyncio.run(coro)
    except RuntimeError:
        # No running loop, so asyncio.run() is safe
        return asyncio.run(coro)