from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


class DefaultImgCB(CallbackData, prefix="dimg"):
    id: str

class GroupCB(CallbackData, prefix="grp"):
    id: int
    action: str
    
    
class TopicCB(CallbackData, prefix="top"):
    chat_id: int
    topic_id: int

class PublishMethodCB(CallbackData, prefix="pubm"):
    method: str


def get_default_images_kb(images) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for img in images:
        builder.button(text=img.name, callback_data=DefaultImgCB(id=str(img.id)))
    builder.button(text="Без картинки", callback_data=DefaultImgCB(id="none"))
    builder.adjust(1)
    return builder.as_markup()

def get_groups_kb(chats, selected_ids: list[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for chat in chats:
        mark = "✅ " if chat.id in selected_ids else "⬜️ "
        builder.button(
            text=f"{mark}{chat.internal_name}", 
            callback_data=GroupCB(id=chat.id, action="toggle")
        )
    
    builder.button(text="➡️ Далее", callback_data=GroupCB(id=0, action="next"))
    builder.adjust(1)
    return builder.as_markup()


def get_topics_kb(chat_id: int, topics) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in topics:
        builder.button(text=t.name, callback_data=TopicCB(chat_id=chat_id, topic_id=t.id))
    builder.adjust(1)
    return builder.as_markup()

def get_publish_method_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡ Опубликовать сразу", callback_data=PublishMethodCB(method="instant"))
    builder.button(text="📅 По расписанию", callback_data=PublishMethodCB(method="schedule"))
    builder.button(text="🗓 По слоту", callback_data=PublishMethodCB(method="slot"))
    builder.adjust(1)
    return builder.as_markup()

def get_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_publish")
    builder.button(text="❌ Отмена", callback_data="cancel_publish")
    builder.adjust(2)
    return builder.as_markup()