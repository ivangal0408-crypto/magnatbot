"""Пакет хендлеров бота.

Порядок подключения роутеров важен: ai_assistant идёт последним, поэтому его
финальный обработчик «неизвестного текста» не перекрывает FSM-сценарии.
"""

from handlers.ai_assistant import router as ai_assistant_router
from handlers.booking import router as booking_router
from handlers.calculator import router as calculator_router
from handlers.contacts import router as contacts_router
from handlers.main_menu import router as main_menu_router

routers = (
    main_menu_router,
    contacts_router,
    calculator_router,
    booking_router,
    ai_assistant_router,
)

__all__ = ["routers"]
