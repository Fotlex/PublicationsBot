from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from web.panel.models import User

class UserMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        from_user = event.from_user

        user, created = await User.objects.aget_or_create(id=from_user.id)
        user.username = from_user.username
        user.first_name = from_user.first_name
        user.last_name = from_user.last_name

        await user.asave()

        data['user'] = user

        return await handler(event, data)
