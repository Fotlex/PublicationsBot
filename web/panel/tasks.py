import json
import time
from contextlib import ExitStack

import requests
from celery import shared_task

from config import config
from .models import Mailing, User


@shared_task
def send_mailing(mailing_id: int):
    mailing = Mailing.objects.get(id=mailing_id)

    attachments = mailing.attachments.all()

    def send_mail(user_id):
        if not attachments:
            requests.post(
                url=f'https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage',
                json={
                    'chat_id': user_id,
                    'text': mailing.text,
                }
            )
            return

        if len(attachments) == 1:
            attachment = attachments[0]
            attachment_type = attachment.type

            if not attachment.file_id:
                with open(attachment.file.path, 'rb') as f:
                    files = {attachment_type: f}
                    response = requests.post(
                        url=f'https://api.telegram.org/bot{config.BOT_TOKEN}/send{attachment_type.capitalize()}',
                        data={
                            'chat_id': user_id,
                            'caption': mailing.text
                        },
                        files=files
                    )

                    if attachment_type == 'photo':
                        file_id = response.json()['result']['photo'][-1]['file_id']
                    else:
                        print(response.json())
                        file_id = response.json()['result'][attachment_type]['file_id']

                    attachment.file_id = file_id
                    attachment.save()
                    return

            requests.post(
                url=f'https://api.telegram.org/bot{config.BOT_TOKEN}/send{attachment_type.capitalize()}',
                data={
                    'chat_id': user_id,
                    'caption': mailing.text,
                    attachment_type: attachment.file_id,
                }
            )
            return

        with ExitStack() as stack:
            media_group = [
                {
                    'type': attachment.type,
                    'media': f'attach://{attachment.file.name}' if not attachment.file_id else attachment.file_id,
                } for attachment in attachments
            ]

            media_group[0]['caption'] = mailing.text

            files = {}
            for attachment in attachments:
                if not attachment.file_id:
                    file_obj = stack.enter_context(open(attachment.file.path, 'rb'))
                    files[attachment.file.name] = file_obj

            response = requests.post(
                f'https://api.telegram.org/bot{config.BOT_TOKEN}/sendMediaGroup',
                data={'chat_id': user_id, 'media': json.dumps(media_group)},
                files=files if files else None
            )

            json_response = response.json()

            for i, attachment in enumerate(attachments):
                if attachment.type == 'photo':
                    attachment.file_id = json_response['result'][i][attachment.type][-1]['file_id']
                else:
                    attachment.file_id = json_response['result'][i][attachment.type]['file_id']
                attachment.save()

    def send_mail_delay(user_id: int):
        send_mail(user_id)
        time.sleep(0.01)

    for user in User.objects.all():
        send_mail_delay(user.id)

    mailing.is_ok = True
    mailing.save()


@shared_task
def example_task():
    print("Пример периодической задачи")
