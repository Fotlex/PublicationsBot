import requests
from celery import shared_task
from django.utils import timezone

from config import config
from .models import Publication


def split_text(text, limit=4096):
    if not text:
        return []
    
    chunks = []
    while len(text) > limit:
        split_at = text.rfind('\n\n', 0, limit)
        if split_at == -1:
            split_at = text.rfind('\n', 0, limit)
            if split_at == -1:
                split_at = text.rfind(' ', 0, limit)
                if split_at == -1:
                    split_at = limit
        
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
        
    if text:
        chunks.append(text.strip())
        
    return chunks


def _send_text(url, base_payload, text):
    payload = base_payload.copy()
    payload['text'] = text
    response = requests.post(url + 'sendMessage', json=payload)
    resp_data = response.json()
    
    if not resp_data.get('ok'):
        raise Exception(resp_data.get('description', 'Ошибка отправки текста'))


def _send_media(url, base_payload, media, caption=""):
    payload = base_payload.copy()
    if caption:
        payload['caption'] = caption
        
    api_method = f'send{media.media_type.capitalize()}'
    
    if media.file_id:
        payload[media.media_type] = media.file_id
        response = requests.post(url + api_method, json=payload)
    elif media.file:
        with open(media.file.path, 'rb') as f:
            files = {media.media_type: f}
            response = requests.post(url + api_method, data=payload, files=files)
    else:
        raise Exception("В медиафайле не указан ни file_id, ни загруженный файл")
        
    resp_data = response.json()
    if not resp_data.get('ok'):
        raise Exception(resp_data.get('description', f'Ошибка отправки {api_method}'))


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
        post.save(update_fields=['status', 'error_message'])
        return

    base_payload = {
        'chat_id': post.chat.chat_id,
        'parse_mode': 'HTML'
    }
    if post.topic and post.topic.thread_id:
        base_payload['message_thread_id'] = post.topic.thread_id

    full_text = post.text or ""
    if post.author and post.author.signature_name:
        full_text += f"\n\nАвтор поста: <b>{post.author.signature_name}</b>"

    url = f'https://api.telegram.org/bot{config.BOT_TOKEN}/'

    try:
        media_files = list(post.media.all())
        visuals = [m for m in media_files if m.media_type in ['photo', 'video']]
        documents = [m for m in media_files if m.media_type == 'document']

        text_fits_caption = len(full_text) <= 1024
        text_sent = False

        for idx, vis in enumerate(visuals):
            if idx == 0 and text_fits_caption and full_text:
                _send_media(url, base_payload, vis, caption=full_text)
                text_sent = True
            else:
                _send_media(url, base_payload, vis, caption="")

        if not text_sent and full_text:
            if not visuals and documents and text_fits_caption:
                pass
            else:
                text_chunks = split_text(full_text, limit=4096)
                for chunk in text_chunks:
                    _send_text(url, base_payload, chunk)
                text_sent = True

        for idx, doc in enumerate(documents):
            if idx == 0 and not text_sent and text_fits_caption and full_text:
                _send_media(url, base_payload, doc, caption=full_text)
                text_sent = True
            else:
                _send_media(url, base_payload, doc, caption="")

        post.status = 'published'
        post.published_at = timezone.now()
        post.error_message = ""
        
    except Exception as e:
        post.status = 'error'
        post.error_message = str(e)

    post.save(update_fields=['status', 'published_at', 'error_message'])
    

@shared_task
def check_scheduled_posts():
    now = timezone.now()
    due_posts = Publication.objects.filter(status='scheduled', scheduled_at__lte=now)
    
    for post in due_posts:
        publish_single_post.delay(post.id)