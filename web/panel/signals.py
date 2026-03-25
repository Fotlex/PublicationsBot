from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Mailing



@receiver(post_save, sender=Mailing)
def mailing_post_save(sender, instance: Mailing, created, **kwargs):
    from .tasks import send_mailing

    if created:
        transaction.on_commit(lambda: send_mailing.apply_async(args=[instance.id], eta=instance.datetime))
