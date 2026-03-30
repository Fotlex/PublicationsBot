from aiogram.fsm.state import State, StatesGroup

class CreatePost(StatesGroup):
    waiting_for_post = State()
    waiting_for_image = State()
    waiting_for_groups = State()
    waiting_for_topics = State()
    waiting_for_publish_method = State()
    waiting_for_datetime = State()