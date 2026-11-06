"""Shared slowapi limiter (login and other sensitive routes use @limiter.limit)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
