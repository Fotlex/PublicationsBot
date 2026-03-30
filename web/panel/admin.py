from django.contrib import admin
from django.utils.html import format_html
from django.template import Engine, Context
from django.http import HttpResponse
from django.db.models import Count
from django.utils import timezone

from .utils import html
from .models import *


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'fio', 'username', 'role', 'phone_number', 'signature_name')
    list_filter = ('role',)
    search_fields = ('id', 'fio', 'username', 'phone_number')
    filter_horizontal = ('allowed_chats',)
    readonly_fields = ('created_at', 'data')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('id', 'fio', 'username', 'phone_number')
        }),
        ('Права и подпись', {
            'fields': ('role', 'signature_name', 'allowed_chats')
        }),
        ('Системные данные', {
            'fields': ('created_at', 'data'),
            'classes': ('collapse',)
        }),
    )


class TopicInline(admin.TabularInline):
    model = Topic
    extra = 0

class SlotInline(admin.TabularInline):
    model = Slot
    extra = 0
    fk_name = 'chat'
    fields = ('day_of_week', 'time')


@admin.register(TelegramChat)
class TelegramChatAdmin(admin.ModelAdmin):
    list_display = ('internal_name', 'chat_type', 'connection_status', 'is_active')
    list_filter = ('chat_type', 'connection_status', 'is_active')
    search_fields = ('internal_name', 'chat_id')
    inlines = [TopicInline, SlotInline]

@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ('get_parent', 'day_of_week', 'time')
    list_filter = ('day_of_week', 'chat', 'topic__chat')
    
    def get_parent(self, obj):
        if obj.topic:
            return f"Топик: {obj.topic.name} (в {obj.topic.chat.internal_name})"
        return f"Группа: {obj.chat.internal_name if obj.chat else '—'}"
    get_parent.short_description = 'Привязка (Группа / Топик)'


@admin.register(DefaultImage)
class DefaultImageAdmin(admin.ModelAdmin):
    list_display = ('name', 'image_preview', 'has_file_id')
    readonly_fields = ('file_id', 'image_preview_large')
    search_fields = ('name',)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 40px; border-radius: 4px;"/>', obj.image.url)
        return "-"
    image_preview.short_description = 'Превью'

    def image_preview_large(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 250px; border-radius: 8px;"/>', obj.image.url)
        return "-"
    image_preview_large.short_description = 'Изображение'

    def has_file_id(self, obj):
        return bool(obj.file_id)
    has_file_id.boolean = True
    has_file_id.short_description = 'Загружено в ТГ'


class PublicationMediaInline(admin.TabularInline):
    model = PublicationMedia
    extra = 0
    readonly_fields = ('file_id',)

@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'topic', 'status', 'publish_method', 'scheduled_at', 'author')
    list_filter = ('status', 'publish_method', 'chat', 'author', 'created_at')
    search_fields = ('text', 'error_message', 'chat__internal_name')
    readonly_fields = ('batch_id', 'created_at', 'published_at', 'error_message')
    inlines = [PublicationMediaInline]
    date_hierarchy = 'scheduled_at'

    fieldsets = (
        ('Контент', {
            'fields': ('text', 'author', 'chat', 'topic')
        }),
        ('Настройки публикации', {
            'fields': ('status', 'publish_method', 'scheduled_at')
        }),
        ('Системная информация', {
            'fields': ('batch_id', 'published_at', 'error_message', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    
@admin.register(PublicationAnalytics)
class AnalyticsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False

    def changelist_view(self, request, extra_context=None):
        now = timezone.now()
        start_date = now.replace(day=1, hour=0, minute=0, second=0)

        pubs = Publication.objects.filter(status='published', published_at__gte=start_date)

        by_group = pubs.values('chat__internal_name').annotate(total=Count('id')).order_by('-total')
        
        by_author = pubs.values('author__fio', 'author__username').annotate(total=Count('id')).order_by('-total')

        authors = User.objects.filter(publications__in=pubs).distinct()
        chats = TelegramChat.objects.filter(publications__in=pubs).distinct()
        
        matrix =[]
        for author in authors:
            row = {'author': author.fio or author.username, 'counts': []}
            for chat in chats:
                row['counts'].append(pubs.filter(author=author, chat=chat).count())
            matrix.append(row)
        
        template = Engine.get_default().from_string(html)
        context = Context({
            'request': request,
            'start_date': start_date,
            'by_group': by_group,
            'by_author': by_author,
            'chats': chats,
            'matrix': matrix,
            'has_permission': True,
            'site_header': self.admin_site.site_header,
        })
        return HttpResponse(template.render(context))