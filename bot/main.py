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

from core.handlers import router
from core.middlewares import UserMiddleware
from aiogram.utils.callback_answer import CallbackAnswerMiddleware


async def main():
    bot = Bot(token=config.BOT_TOKEN)

    dp = Dispatcher()
    dp.callback_query.outer_middleware(CallbackAnswerMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())
    dp.message.outer_middleware(UserMiddleware())
    dp.include_router(router)

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
