import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.core.settings')

app = Celery('bot-template')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'check-scheduled-posts-every-minute': {
        'task': 'web.panel.tasks.check_scheduled_posts',
        'schedule': crontab(minute='*/1'),
    },
}
