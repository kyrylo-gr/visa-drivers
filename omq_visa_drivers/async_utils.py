"""Async utils."""
import threading


def sleep(delay):
    """Sleep function using threading. Allows not to block subprocesses"""
    event = threading.Event()
    event.wait(delay)
    event.clear()
