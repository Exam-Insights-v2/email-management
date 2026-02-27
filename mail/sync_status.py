"""Sync status per account (in progress / last error) via cache for UI feedback."""
from django.core.cache import cache

SYNC_IN_PROGRESS_KEY = "mail:sync_in_progress:{account_id}"
LAST_SYNC_ERROR_KEY = "mail:last_sync_error:{account_id}"
SYNC_LOCK_KEY = "mail:sync_lock:{account_id}"
STATUS_SYNC_WINDOW_KEY = "mail:status_sync_window:{account_id}"
SYNC_IN_PROGRESS_TIMEOUT = 3600  # 1 hour; clears if worker dies
LAST_SYNC_ERROR_TIMEOUT = 86400  # 24 hours


def set_sync_in_progress(account_id: int, in_progress: bool) -> None:
    if in_progress:
        cache.set(SYNC_IN_PROGRESS_KEY.format(account_id=account_id), True, SYNC_IN_PROGRESS_TIMEOUT)
    else:
        cache.delete(SYNC_IN_PROGRESS_KEY.format(account_id=account_id))


def get_sync_in_progress(account_id: int) -> bool:
    return bool(cache.get(SYNC_IN_PROGRESS_KEY.format(account_id=account_id)))


def set_last_sync_error(account_id: int, error_message: str) -> None:
    cache.set(
        LAST_SYNC_ERROR_KEY.format(account_id=account_id),
        error_message[:500],
        LAST_SYNC_ERROR_TIMEOUT,
    )


def clear_last_sync_error(account_id: int) -> None:
    cache.delete(LAST_SYNC_ERROR_KEY.format(account_id=account_id))


def get_last_sync_error(account_id: int) -> str:
    return cache.get(LAST_SYNC_ERROR_KEY.format(account_id=account_id)) or ""


def acquire_sync_lock(account_id: int, timeout_seconds: int = 300) -> bool:
    """
    Acquire an account-scoped lock for sync execution.
    Returns True if lock acquired; False if another worker already holds it.
    """
    return bool(
        cache.add(
            SYNC_LOCK_KEY.format(account_id=account_id),
            "1",
            timeout=timeout_seconds,
        )
    )


def release_sync_lock(account_id: int) -> None:
    cache.delete(SYNC_LOCK_KEY.format(account_id=account_id))


def should_run_status_sync(account_id: int, min_interval_seconds: int) -> bool:
    """
    Debounce status sync to avoid expensive per-email provider checks every run.
    Uses cache.add so only the first run inside the window returns True.
    """
    if min_interval_seconds <= 0:
        return True
    return bool(
        cache.add(
            STATUS_SYNC_WINDOW_KEY.format(account_id=account_id),
            "1",
            timeout=min_interval_seconds,
        )
    )
