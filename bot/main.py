import logging
from pathlib import Path
import django
import sys
import os

sys.path.append(str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.core.settings")
django.setup()

from aiogram import Bot, Dispatcher
from config import config
import asyncio

from aiogram.client.session.aiohttp import AiohttpSession

from core.handlers import post, chat_events
from core.middlewares import UserMiddleware
from aiogram.utils.callback_answer import CallbackAnswerMiddleware
from aiogram.types import BotCommand


async def main():
    session = AiohttpSession(proxy=config.PROXI)
    
    bot = Bot(token=config.BOT_TOKEN, session=session)

    dp = Dispatcher()
    dp.callback_query.outer_middleware(CallbackAnswerMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())
    dp.message.outer_middleware(UserMiddleware())
    
    main_menu_commands = [
        BotCommand(command='/regtopic', description='Зарегестрировать топик'),
    ]
    await bot.set_my_commands(main_menu_commands)
    
    dp.include_routers(
        post.router,
        chat_events.router,
    )

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
