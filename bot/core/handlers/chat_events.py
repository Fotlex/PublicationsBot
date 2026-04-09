from aiogram import Router
from aiogram.types import ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, PROMOTED_TRANSITION, IS_MEMBER, IS_NOT_MEMBER
from web.panel.models import TelegramChat

router = Router()

@router.my_chat_member()
async def bot_added_to_chat(event: ChatMemberUpdated):
    chat = event.chat
    new_state = event.new_chat_member.status

    if new_state in ['administrator', 'member']:
        connection_status = 'active'
    elif new_state in ['restricted']:
        connection_status = 'no_rights'
    else:
        connection_status = 'no_bot'

    tg_chat, created = await TelegramChat.objects.aget_or_create(
        chat_id=chat.id,
        defaults={
            'internal_name': chat.title or f"Chat {chat.id}",
            'chat_type': 'channel' if chat.type == 'channel' else 'group',
            'connection_status': connection_status,
            'is_active': True
        }
    )

    if not created:
        tg_chat.connection_status = connection_status
        if chat.title:
            tg_chat.internal_name = chat.title
        await tg_chat.asave()