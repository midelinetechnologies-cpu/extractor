import logging
import functools
import traceback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

_log = logging.getLogger("extractor")


def log_call(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        name = fn.__qualname__
        _log.info("START  %s", name)
        try:
            result = fn(*args, **kwargs)
            _log.info("END    %s", name)
            return result
        except Exception as exc:
            _log.error(
                "ERROR  %s | %s: %s\n%s",
                name,
                type(exc).__name__,
                exc,
                traceback.format_exc(),
            )
            raise
    return wrapper
