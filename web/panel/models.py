import uuid
from django.db import models
from django.core.exceptions import ValidationError

class TelegramChat(models.Model):
    TYPE_CHOICES = (
        ('group', 'Обычная группа'),
        ('topic_group', 'Группа с топиками'),
        ('channel', 'Канал'),
    )
    
    STATUS_CHOICES = (
        ('active', '✅ Активна'),
        ('no_bot', '⚠️ Бот не добавлен'),
        ('no_rights', '⚠️ Недостаточно прав'),
        ('error', '❌ Ошибка'),
    )

    chat_id = models.BigIntegerField('ID чата', unique=True, null=True, blank=True)
    internal_name = models.CharField('Внутреннее название', max_length=150)
    tme_link = models.URLField('Ссылка (t.me)', max_length=200, blank=True, null=True)
    
    chat_type = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES, default='channel')
    connection_status = models.CharField('Статус подключения', max_length=20, choices=STATUS_CHOICES, default='no_bot')
    is_active = models.BooleanField('Активность (вкл/выкл)', default=True)

    restrict_posting_until = models.DateTimeField(
        'Ограничение отправки новых постов до:',
        null=True, blank=True,
        help_text='Если дата указана и еще не наступила, все новые мгновенные и слотовые посты будут отправлены не раньше этого времени.'
    )
    
    def __str__(self):
        return self.internal_name

    class Meta:
        verbose_name = 'Группа / Канал'
        verbose_name_plural = 'Группы и Каналы'


class User(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Суперадмин'),
        ('author', 'Автор публикаций'),
        ('viewer', 'Наблюдатель'), 
    )
    
    id = models.BigIntegerField('TG ID', primary_key=True)
    fio = models.CharField('ФИО', max_length=150, null=True, blank=True)
    username = models.CharField('Юзернейм', max_length=64, null=True, blank=True)
    phone_number = models.CharField('Номер телефона', max_length=20, null=True, blank=True)
    
    signature_name = models.CharField('Отображаемое имя для подписи постов', max_length=100, null=True, blank=True)
    role = models.CharField('Роль', max_length=10, choices=ROLE_CHOICES, default='author')
    
    allowed_chats = models.ManyToManyField(TelegramChat, verbose_name='Доступные группы/каналы', blank=True)
    
    created_at = models.DateTimeField('Дата регистрации', auto_now_add=True)
    data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.fio or self.username or self.id} [{self.get_role_display()}]"

    class Meta:
        verbose_name = 'Пользователь системы'
        verbose_name_plural = 'Авторы и Администраторы'


class Topic(models.Model):
    chat = models.ForeignKey(TelegramChat, on_delete=models.CASCADE, related_name='topics', verbose_name='Группа')
    thread_id = models.IntegerField('ID топика (thread_id)')
    name = models.CharField('Название топика', max_length=150)
    is_active = models.BooleanField('Активность', default=True)

    def __str__(self):
        return f"{self.chat.internal_name} -> {self.name}"

    class Meta:
        verbose_name = 'Топик'
        verbose_name_plural = 'Топики'
        unique_together = ('chat', 'thread_id')


class Slot(models.Model):
    DAY_CHOICES = (
        (0, 'Понедельник'),
        (1, 'Вторник'),
        (2, 'Среда'),
        (3, 'Четверг'),
        (4, 'Пятница'),
        (5, 'Суббота'),
        (6, 'Воскресенье'),
    )
    
    chat = models.ForeignKey(TelegramChat, on_delete=models.CASCADE, related_name='slots', verbose_name='Группа/Канал', null=True, blank=True)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='slots', verbose_name='Топик', null=True, blank=True)
    
    day_of_week = models.IntegerField('День недели', choices=DAY_CHOICES)
    time = models.TimeField('Время публикации (ЧЧ:ММ)')
    
    def clean(self):
        if not self.chat and not self.topic:
            raise ValidationError("Слот должен быть привязан к группе или топику.")
        if self.chat and self.topic:
            raise ValidationError("Слот не может быть одновременно привязан и к группе, и к топику.")
        if self.topic and self.topic.chat.chat_type != 'topic_group':
            raise ValidationError("Выбранный топик не принадлежит группе с топиками.")
            
    def __str__(self):
        parent = self.topic.name if self.topic else self.chat.internal_name
        return f"{parent} | {self.get_day_of_week_display()} в {self.time.strftime('%H:%M')}"

    class Meta:
        verbose_name = 'Слот публикации'
        verbose_name_plural = 'Слоты публикаций (Неделя)'
        ordering =['day_of_week', 'time']


class DefaultImage(models.Model):
    name = models.CharField('Название (для кнопки)', max_length=50)
    image = models.ImageField('Картинка', upload_to='default_images/')
    file_id = models.CharField('File ID (Телеграм)', max_length=255, null=True, blank=True, help_text='Заполнится автоматически при первой отправке ботом')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Дефолтная картинка'
        verbose_name_plural = 'Раздел: Картинки'


class Publication(models.Model):
    STATUS_CHOICES = (
        ('draft', '📝 Черновик'),
        ('scheduled', '⏳ Запланирован'),
        ('published', '✅ Опубликован'),
        ('error', '❌ Ошибка'),
    )
    
    METHOD_CHOICES = (
        ('instant', 'Мгновенно'),
        ('scheduled', 'По расписанию'),
        ('slot', 'По слоту'),
    )

    batch_id = models.UUIDField(default=uuid.uuid4, editable=False)

    text = models.TextField('Текст с форматированием', blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='publications', verbose_name='Автор')
    
    chat = models.ForeignKey(TelegramChat, on_delete=models.CASCADE, related_name='publications', verbose_name='Группа/Канал')
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Топик')
    
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='draft')
    publish_method = models.CharField('Способ публикации', max_length=20, choices=METHOD_CHOICES, default='instant')
    
    scheduled_at = models.DateTimeField('Запланировано на', null=True, blank=True)
    published_at = models.DateTimeField('Фактическое время публикации', null=True, blank=True)
    
    error_message = models.TextField('Текст ошибки', blank=True, null=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    def __str__(self):
        return f"Пост #{self.id} -> {self.chat.internal_name}[{self.get_status_display()}]"

    class Meta:
        verbose_name = 'Публикация (Пост)'
        verbose_name_plural = 'Очередь постов'
        ordering =['-created_at']


class PublicationMedia(models.Model):
    TYPE_CHOICES = (
        ('photo', 'Фото'),
        ('video', 'Видео'),
        ('document', 'Документ')
    )

    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='media', verbose_name='Публикация')
    media_type = models.CharField('Тип медиа', max_length=20, choices=TYPE_CHOICES)
    file_id = models.CharField('File ID (Телеграм)', max_length=255, blank=True, null=True)
    file = models.FileField('Файл (из админки)', upload_to='publications_media/', blank=True, null=True)

    class Meta:
        verbose_name = 'Медиафайл'
        verbose_name_plural = 'Медиафайлы публикации'
        
        
class PublicationAnalytics(Publication):
    class Meta:
        proxy = True
        verbose_name = 'Аналитика и Статистика'
        verbose_name_plural = '📊 Аналитика'