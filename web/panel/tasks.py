import requests
from celery import shared_task
from django.utils import timezone

from config import config
from .models import Publication

@shared_task
def publish_single_post(post_id: int):
    try:
        post = Publication.objects.get(id=post_id)
    except Publication.DoesNotExist:
        return

    if post.status != 'scheduled':
        return

    if not post.chat.chat_id:
        post.status = 'error'
        post.error_message = "Ошибка: В админке не указан реальный chat_id для этой группы!"
        post.save()
        return

    payload = {
        'chat_id': post.chat.chat_id,
        'parse_mode': 'HTML'
    }

    if post.topic and post.topic.thread_id:
        payload['message_thread_id'] = post.topic.thread_id

    text = post.text or ""
    if post.author and post.author.signature_name:
        text += f"\n\nАвтор поста: <b>{post.author.signature_name}</b>"

    media = post.media.first()
    url = f'https://api.telegram.org/bot{config.BOT_TOKEN}/'

    try:
        if not media:
            payload['text'] = text
            response = requests.post(url + 'sendMessage', json=payload)
        else:
            payload['caption'] = text
            payload[media.media_type] = media.file_id
            
            api_method = f'send{media.media_type.capitalize()}'
            response = requests.post(url + api_method, json=payload)

        resp_data = response.json()
        
        if resp_data.get('ok'):
            post.status = 'published'
            post.published_at = timezone.now()
            post.error_message = ""
        else:
            post.status = 'error'
            post.error_message = resp_data.get('description', 'Неизвестная ошибка API')
            
    except Exception as e:
        post.status = 'error'
        post.error_message = str(e)

    post.save()


@shared_task
def check_scheduled_posts():
    now = timezone.now()
    due_posts = Publication.objects.filter(status='scheduled', scheduled_at__lte=now)
    
    for post in due_posts:
        publish_single_post.delay(post.id)