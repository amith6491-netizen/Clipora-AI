import threading


class ProcessingCancelledError(Exception):
    """Raised when an active AI processing pipeline job is cancelled by the user."""


def raise_if_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ProcessingCancelledError("Processing cancelled by user.")
