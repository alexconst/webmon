import asyncio


class TooManyTriesException(Exception):
    """Custom exception raised when a function fails to execute successfully after the maximum number of retry attempts.
    """
    pass


def retry(**kwargs):
    """A decorator for retrying a given function asynchronously with configurable retry parameters.

    This decorator wraps around an asynchronous function and automatically retries its execution
    if it raises an exception. The number of retries, delay between retries, backoff factor,
    maximum delay, and a logger instance can be configured through keyword arguments.

    :param kwargs: keyword arguments to configure the retry behavior:
        - `tries`: int, optional
            Maximum number of retry attempts, default is 3.
        - `delay`: float, optional
            Initial delay between retries in seconds, default is 2.
        - `backoff`: float, optional
            Factor by which the delay increases after each unsuccessful attempt, default is 1.
        - `max_interval`: float, optional
            Maximum amount of time between retries in seconds, default is None (no limit).
        - `logger`: logging.Logger, optional
            Logger instance for logging retry attempts and errors, default is None.

    :return: the original function wrapped with retry logic.
    :rtype: callable
    """

    tries = kwargs.get('tries', 3)
    delay = kwargs.get('delay', 2)
    backoff = kwargs.get('backoff', 1)
    max_interval = kwargs.get('max_interval', None)
    logger = kwargs.get('logger', None)

    def decorator(func):

        async def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(tries):
                try:
                    if logger:
                        logger.debug(f"{func.__name__} will attempt {attempt + 1} of {tries}")
                    return await func(*args, **kwargs)
                except Exception as exc:
                    if logger:
                        msg = f"Error on attempt {attempt + 1}. Will sleep for {current_delay} seconds."
                        msg += f" Exception: {exc.__class__} Error message: {str(exc)}"
                        logger.error(msg)
                    current_delay *= backoff
                    if current_delay > max_interval:
                        current_delay = max_interval
                    await asyncio.sleep(current_delay)
            raise TooManyTriesException(f"{func.__name__} failed after {tries} attempts")

        return wrapper

    return decorator
