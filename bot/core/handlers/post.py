import uuid
from datetime import datetime, timedelta
from asgiref.sync import sync_to_async
from django.utils import timezone
import dateutil.parser

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

from core.states import CreatePost
from core.keyboards import (
    get_default_images_kb, get_groups_kb, get_topics_kb,
    get_publish_method_kb, get_confirm_kb,
    DefaultImgCB, GroupCB, TopicCB, PublishMethodCB
)
from web.panel.models import DefaultImage, User, TelegramChat, Topic, Slot, Publication, PublicationMedia

router = Router()

@sync_to_async
def get_user_chats(user_id: int):
    user = User.objects.get(id=user_id)
    return list(user.allowed_chats.filter(is_active=True))

@router.message(CommandStart())
async def cmd_start(message: Message, user: User, state: FSMContext):
    await state.clear()
    await message.answer(
        f"👋 Привет, {user.fio or message.from_user.first_name}!\n\n"
        "Отправьте или перешлите мне сообщение, которое хотите опубликовать."
    )
    await state.set_state(CreatePost.waiting_for_post)

@router.message(CreatePost.waiting_for_post)
async def receive_post(message: Message, state: FSMContext):
    text = message.html_text or ""
    media_type, file_id = None, None
    
    if message.photo:
        media_type, file_id = 'photo', message.photo[-1].file_id
    elif message.video:
        media_type, file_id = 'video', message.video.file_id
    elif message.document:
        media_type, file_id = 'document', message.document.file_id

    await state.update_data(post_data={'text': text, 'media_type': media_type, 'file_id': file_id})

    if not media_type:
        images = [img async for img in DefaultImage.objects.all()]
        if images:
            await message.answer("Выберите картинку для поста:", reply_markup=get_default_images_kb(images))
            await state.set_state(CreatePost.waiting_for_image)
            return

    await show_groups_menu(message, state, message.from_user.id)


@router.callback_query(DefaultImgCB.filter(), CreatePost.waiting_for_image)
async def process_default_image(callback: CallbackQuery, callback_data: DefaultImgCB, state: FSMContext, bot: Bot):
    if callback_data.id != "none":
        img = await DefaultImage.objects.aget(id=int(callback_data.id))
        if not img.file_id:
            msg = await bot.send_photo(chat_id=callback.from_user.id, photo=FSInputFile(img.image.path))
            img.file_id = msg.photo[-1].file_id
            await img.asave(update_fields=['file_id'])
            await msg.delete()
        
        data = await state.get_data()
        data['post_data'].update({'media_type': 'photo', 'file_id': img.file_id})
        await state.update_data(post_data=data['post_data'])

    await show_groups_menu(callback.message, state, callback.from_user.id)


async def show_groups_menu(message: Message | CallbackQuery, state: FSMContext, user_id: int):
    msg = message if isinstance(message, Message) else message.message
    chats = await get_user_chats(user_id)
    if not chats:
        await msg.answer("У вас нет доступных групп. Обратитесь к админу.")
        await state.clear()
        return

    await state.update_data(selected_groups=[])
    text = "Выберите группы для рассылки (можно несколько) и нажмите «Далее»:"
    if isinstance(message, CallbackQuery):
        await msg.edit_text(text, reply_markup=get_groups_kb(chats,[]))
    else:
        await msg.answer(text, reply_markup=get_groups_kb(chats,[]))
    await state.set_state(CreatePost.waiting_for_groups)


@router.callback_query(GroupCB.filter(), CreatePost.waiting_for_groups)
async def process_groups_selection(callback: CallbackQuery, callback_data: GroupCB, state: FSMContext):
    data = await state.get_data()
    selected_groups = data.get('selected_groups',[])
    
    if callback_data.action == "next":
        if not selected_groups:
            await callback.answer("Выберите хотя бы одну группу!", show_alert=True)
            return
            
        selected_chats = await sync_to_async(list)(TelegramChat.objects.filter(id__in=selected_groups))
        topic_groups = [c.id for c in selected_chats if c.chat_type == 'topic_group']
        
        await state.update_data(pending_topic_groups=topic_groups, selected_topics={})
        
        if topic_groups:
            await ask_next_topic(callback.message, state)
        else:
            await ask_publish_method(callback.message, state)
        return

    chat_id = callback_data.id
    if chat_id in selected_groups:
        selected_groups.remove(chat_id)
    else:
        selected_groups.append(chat_id)
        
    await state.update_data(selected_groups=selected_groups)
    chats = await get_user_chats(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=get_groups_kb(chats, selected_groups))


async def ask_next_topic(message: Message, state: FSMContext):
    data = await state.get_data()
    pending = data.get('pending_topic_groups',[])
    
    if not pending:
        await ask_publish_method(message, state)
        return

    chat_id = pending[0]
    chat = await TelegramChat.objects.aget(id=chat_id)
    topics = await sync_to_async(list)(Topic.objects.filter(chat_id=chat_id, is_active=True))

    if not topics:
        pending.pop(0)
        await state.update_data(pending_topic_groups=pending)
        await ask_next_topic(message, state)
        return

    text = f"Выберите топик для группы <b>{chat.internal_name}</b>:"
    await message.edit_text(text, reply_markup=get_topics_kb(chat_id, topics), parse_mode="HTML")
    await state.set_state(CreatePost.waiting_for_topics)


@router.callback_query(TopicCB.filter(), CreatePost.waiting_for_topics)
async def process_topic_selection(callback: CallbackQuery, callback_data: TopicCB, state: FSMContext):
    data = await state.get_data()
    selected_topics = data.get('selected_topics', {})
    selected_topics[callback_data.chat_id] = callback_data.topic_id

    pending = data.get('pending_topic_groups',[])
    if pending:
        pending.pop(0)

    await state.update_data(selected_topics=selected_topics, pending_topic_groups=pending)
    await ask_next_topic(callback.message, state)


async def ask_publish_method(message: Message, state: FSMContext):
    await message.edit_text("Выберите способ публикации:", reply_markup=get_publish_method_kb())
    await state.set_state(CreatePost.waiting_for_publish_method)


@router.callback_query(PublishMethodCB.filter(), CreatePost.waiting_for_publish_method)
async def process_publish_method(callback: CallbackQuery, callback_data: PublishMethodCB, state: FSMContext):
    method = callback_data.method
    await state.update_data(publish_method=method)

    if method == "instant":
        await save_publications(callback, state)
    elif method == "schedule":
        await callback.message.edit_text(
            "Введите дату и время публикации в формате:\n`ДД.ММ.ГГГГ ЧЧ:ММ`\nНапример: 31.12.2026 15:30", 
            parse_mode="Markdown"
        )
        await state.set_state(CreatePost.waiting_for_datetime)
    elif method == "slot":
        await callback.answer("Расчет слотов...")
        await calculate_and_show_slots(callback, state)


@router.message(CreatePost.waiting_for_datetime)
async def process_datetime(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        await state.update_data(scheduled_time=dt.isoformat())
        await message.answer(f"Запланировано на {dt.strftime('%d.%m.%Y %H:%M')}.\nПодтверждаете?", reply_markup=get_confirm_kb())
    except ValueError:
        await message.answer("Неверный формат! Введите дату в формате: `ДД.ММ.ГГГГ ЧЧ:ММ`", parse_mode="Markdown")


@sync_to_async
def _get_next_slots(selected_groups, selected_topics):
    now = timezone.now()
    results = {}
    for chat_id in selected_groups:
        topic_id = selected_topics.get(chat_id)
        
        if topic_id:
            slots = Slot.objects.filter(topic_id=topic_id).order_by('day_of_week', 'time')
        else:
            slots = Slot.objects.filter(chat_id=chat_id).order_by('day_of_week', 'time')

        if not slots.exists():
            results[chat_id] = {"error": "Нет настроенных слотов"}
            continue

        slots = list(slots)
        current_weekday = now.weekday()
        current_time = now.time()
        best_slot_dt = None


        for i in range(8):
            check_day = (current_weekday + i) % 7
            for slot in slots:
                if slot.day_of_week == check_day:
                    if i == 0 and slot.time <= current_time:
                        continue
                    target_date = now.date() + timedelta(days=i)
                    best_slot_dt = timezone.make_aware(datetime.combine(target_date, slot.time))
                    break
            if best_slot_dt:
                break

        results[chat_id] = {"dt": best_slot_dt} if best_slot_dt else {"error": "Слоты настроены криво"}
    return results


async def calculate_and_show_slots(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    slots_info = await _get_next_slots(data['selected_groups'], data.get('selected_topics', {}))

    text_lines = ["🗓 Ближайшие слоты для публикации:\n"]
    slot_times, can_publish = {}, True
    
    chats = await sync_to_async(list)(TelegramChat.objects.filter(id__in=data['selected_groups']))
    chat_dict = {c.id: c.internal_name for c in chats}

    for chat_id, info in slots_info.items():
        chat_name = chat_dict.get(chat_id, "Группа")
        if "error" in info:
            text_lines.append(f"❌ {chat_name}: {info['error']}")
            can_publish = False
        else:
            dt = info['dt']
            slot_times[str(chat_id)] = dt.isoformat()
            text_lines.append(f"✅ {chat_name}: {dt.strftime('%d.%m.%Y %H:%M')}")

    await state.update_data(slot_times=slot_times)

    if not can_publish:
        text_lines.append("\n⚠️ У некоторых групп не настроены слоты. Настройте их в админке или выберите другой способ.")
        await callback.message.edit_text("\n".join(text_lines), reply_markup=get_publish_method_kb())
        return

    text_lines.append("\nПодтверждаете постановку в эти слоты?")
    await callback.message.edit_text("\n".join(text_lines), reply_markup=get_confirm_kb())


@router.callback_query(F.data == "cancel_publish")
async def cancel_publish(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Публикация отменена. Можете отправить новый пост.")


@router.callback_query(F.data == "confirm_publish")
async def confirm_publish(callback: CallbackQuery, state: FSMContext):
    await save_publications(callback, state)


async def save_publications(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await User.objects.aget(id=callback.from_user.id)
    
    @sync_to_async
    def _create_posts():
        batch_id = uuid.uuid4()
        method = data['publish_method']
        
        for chat_id in data['selected_groups']:
            topic_id = data.get('selected_topics', {}).get(chat_id)
            
            if method == "schedule":
                dt_naive = dateutil.parser.isoparse(data['scheduled_time'])
                pub_scheduled_at = timezone.make_aware(dt_naive)
            elif method == "slot":
                pub_scheduled_at = dateutil.parser.isoparse(data['slot_times'][str(chat_id)])
            else:
                pub_scheduled_at = timezone.now()

            pub = Publication.objects.create(
                batch_id=batch_id,
                text=data['post_data']['text'],
                author=user,
                chat_id=chat_id,
                topic_id=topic_id,
                status='scheduled',
                publish_method=method,
                scheduled_at=pub_scheduled_at
            )

            if data['post_data'].get('media_type'):
                PublicationMedia.objects.create(
                    publication=pub,
                    media_type=data['post_data']['media_type'],
                    file_id=data['post_data']['file_id']
                )

    await _create_posts()
    await state.clear()
    
    method = data.get('publish_method')
    msg = "✅ Посты отправлены в очередь на мгновенную публикацию!" if method == "instant" else "✅ Посты успешно запланированы!"
    await callback.message.edit_text(msg)