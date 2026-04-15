from aiogram import Router, F
from aiogram.types import ChatMemberUpdated, Message
from aiogram.filters import Command
from web.panel.models import TelegramChat, Topic

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

    chat_type = 'channel' if chat.type == 'channel' else ('topic_group' if getattr(chat, 'is_forum', False) else 'group')

    tg_chat, created = await TelegramChat.objects.aget_or_create(
        chat_id=chat.id,
        defaults={
            'internal_name': chat.title or f"Chat {chat.id}",
            'chat_type': chat_type,
            'connection_status': connection_status,
            'is_active': True
        }
    )

    if not created:
        tg_chat.connection_status = connection_status
        tg_chat.chat_type = chat_type
        if chat.title:
            tg_chat.internal_name = chat.title
        await tg_chat.asave()


@router.message(F.forum_topic_created | F.forum_topic_edited | F.forum_topic_closed | F.forum_topic_reopened)
async def on_forum_topic_action(message: Message):
    chat = message.chat
    thread_id = message.message_thread_id
    
    tg_chat, _ = await TelegramChat.objects.aget_or_create(
        chat_id=chat.id,
        defaults={
            'internal_name': chat.title or f"Chat {chat.id}",
            'chat_type': 'topic_group',
            'connection_status': 'active',
            'is_active': True
        }
    )
    
    if tg_chat.chat_type != 'topic_group':
        tg_chat.chat_type = 'topic_group'
        await tg_chat.asave()

    is_active = True
    name = None

    if message.forum_topic_created:
        name = message.forum_topic_created.name
    elif message.forum_topic_edited:
        name = message.forum_topic_edited.name
    elif message.forum_topic_closed:
        is_active = False
    elif message.forum_topic_reopened:
        is_active = True

    defaults = {'is_active': is_active}
    
    if name:
        defaults['name'] = name
    else:
        has_topic = await Topic.objects.filter(chat=tg_chat, thread_id=thread_id).aexists()
        if not has_topic:
            defaults['name'] = f"Топик {thread_id}"

    await Topic.objects.aupdate_or_create(
        chat=tg_chat,
        thread_id=thread_id,
        defaults=defaults
    )


@router.message(Command("regtopic"))
async def cmd_register_topic(message: Message):
    if getattr(message.chat, 'is_forum', False) is False or not message.message_thread_id:
        await message.answer("⚠️ Эту команду нужно писать внутри конкретного топика!")
        return

    name = message.text.replace("/regtopic", "").strip()
    if not name:
        await message.answer("⚠️ Пожалуйста, укажите название топика. Пример:\n`/regtopic Важное`", parse_mode="Markdown")
        return

    tg_chat = await TelegramChat.objects.aget(chat_id=message.chat.id)
    
    await Topic.objects.aupdate_or_create(
        chat=tg_chat,
        thread_id=message.message_thread_id,
        defaults={'name': name, 'is_active': True}
    )
    
    await message.answer(f"✅ Топик <b>{name}</b> успешно сохранен в базу данных!", parse_mode="HTML")