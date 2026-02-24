"""Sync status per account (in progress / last error) via cache for UI feedback."""
from django.core.cache import cache

SYNC_IN_PROGRESS_KEY = "mail:sync_in_progress:{account_id}"
LAST_SYNC_ERROR_KEY = "mail:last_sync_error:{account_id}"
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
