# __init__.py
"""
Модуль промокодов
"""

from .promo_manager import PromoCodeManager, promo_manager
from .promo_utils import (
    send_promo_code_to_user_async,
    get_promo_stats_formatted,
    get_user_promocodes,
    format_user_promocodes
)
from .admin_commands import router as promo_router

__all__ = [
    'PromoCodeManager',
    'promo_manager',
    'send_promo_code_to_user_async',
    'get_promo_stats_formatted',
    'get_user_promocodes',
    'format_user_promocodes',
    'promo_router'
]
