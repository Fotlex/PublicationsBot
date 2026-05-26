from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


class DefaultImgCB(CallbackData, prefix="dimg"):
    id: str
    

class DefaultImgPageCB(CallbackData, prefix="dimpg"):
    page: int    


class GroupCB(CallbackData, prefix="grp"):
    id: int
    action: str
    
    
class TopicCB(CallbackData, prefix="top"):
    chat_id: int
    topic_id: int

class PublishMethodCB(CallbackData, prefix="pubm"):
    method: str


def get_default_images_kb(images: list, page: int = 0, items_per_page: int = 90) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_images = images[start_idx:end_idx]
    
    for img in page_images:
        builder.button(text=img.name, callback_data=DefaultImgCB(id=str(img.id)))
        
    builder.adjust(2) 
    
    total_pages = (len(images) + items_per_page - 1) // items_per_page
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=DefaultImgPageCB(page=page-1).pack()))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=DefaultImgPageCB(page=page+1).pack()))
        
    if nav_buttons:
        builder.row(*nav_buttons)
        
    builder.row(InlineKeyboardButton(text="Без картинки", callback_data=DefaultImgCB(id="none").pack()))
    
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


def get_finish_post_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Завершить ввод текста", callback_data="finish_post_input")
    builder.button(text="❌ Отменить", callback_data="cancel_publish")
    builder.adjust(1)
    return builder.as_markup()