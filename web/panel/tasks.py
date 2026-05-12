import requests
import json
from celery import shared_task
from django.utils import timezone

from config import config
from .models import Publication


def get_proxies():
    if getattr(config, 'PROXI', None):
        return {'http': config.PROXI, 'https': config.PROXI}
    return None


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
    response = requests.post(url + 'sendMessage', json=payload, proxies=get_proxies())
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
        response = requests.post(url + api_method, json=payload, proxies=get_proxies())
    elif media.file:
        with open(media.file.path, 'rb') as f:
            files = {media.media_type: f}
            response = requests.post(url + api_method, data=payload, files=files, proxies=get_proxies())
    else:
        raise Exception("В медиафайле не указан ни file_id, ни загруженный файл")
        
    resp_data = response.json()
    if not resp_data.get('ok'):
        raise Exception(resp_data.get('description', f'Ошибка отправки {api_method}'))


def _send_media_group(url, base_payload, media_list, caption=""):
    payload = base_payload.copy()
    media_json = []
    files = {}

    for idx, m in enumerate(media_list):
        media_item = {'type': m.media_type, 'parse_mode': 'HTML'}
        if idx == 0 and caption:
            media_item['caption'] = caption

        if m.file_id:
            media_item['media'] = m.file_id
        elif m.file:
            attach_name = f'file_{idx}'
            media_item['media'] = f'attach://{attach_name}'
            files[attach_name] = open(m.file.path, 'rb')
        else:
            continue
        media_json.append(media_item)

    payload['media'] = json.dumps(media_json)
    try:
        if files:
            res = requests.post(url + 'sendMediaGroup', data=payload, files=files, proxies=get_proxies())
        else:
            res = requests.post(url + 'sendMediaGroup', json=payload, proxies=get_proxies())
    finally:
        for f in files.values(): f.close()
    
    if not res.json().get('ok'):
        raise Exception(res.json().get('description', 'Ошибка альбома'))

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

        if visuals:
            caption = full_text if text_fits_caption else ""
            if len(visuals) > 1:
                _send_media_group(url, base_payload, visuals, caption=caption)
            else:
                _send_media(url, base_payload, visuals[0], caption=caption)
            if caption:
                text_sent = True

        if not text_sent and full_text:
            for chunk in split_text(full_text, limit=4096):
                _send_text(url, base_payload, chunk)
            text_sent = True

        for doc in documents:
            _send_media(url, base_payload, doc, caption="")
            
        post.published_at = timezone.now()
        post.status = 'published'
        
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