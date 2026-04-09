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
        if getattr(event, "chat", None) and event.chat.type != "private":
            return await handler(event, data)
        
        from_user = event.from_user


        user, created = await User.objects.aget_or_create(
            id=from_user.id,
            defaults={
                'username': from_user.username,
                'fio': from_user.full_name,
                'role': ''
            }
        )

        update_fields =[]
        if user.username != from_user.username:
            user.username = from_user.username
            update_fields.append('username')
        if not user.fio and from_user.full_name:
            user.fio = from_user.full_name
            update_fields.append('fio')

        if update_fields:
            await user.asave(update_fields=update_fields)

        if not user.role:
            text = (
                "⏳ Вы добавлены в базу данных!\n\n"
                "Ожидайте, пока администратор выдаст вам права (назначит роль "
                "и выберет доступные группы). После этого вы сможете публиковать посты."
            )
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            return

        data['user'] = user
        return await handler(event, data)