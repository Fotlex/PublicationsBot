html = r"""
{% extends "admin/base_site.html" %}
{% block content %}
<style>
    .stat-card { background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
    .stat-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }
    .stat-table th, .stat-table td { border: 1px solid #e0e0e0; padding: 10px; text-align: left; }
    .stat-table th { background-color: #f8f9fa; font-weight: bold; }
</style>

<div class="stat-card">
    <h2 style="margin: 0; color: #333;">📊 Статистика за текущий месяц (с {{ start_date|date:"d.m.Y" }})</h2>
</div>

<div style="display: flex; gap: 20px; flex-wrap: wrap;">
    <div class="stat-card" style="flex: 1; min-width: 300px;">
        <h3>🏢 Публикации по группам</h3>
        <table class="stat-table">
            <tr><th>Группа</th><th>Количество постов</th></tr>
            {% for item in by_group %}
            <tr><td>{{ item.chat__internal_name }}</td><td><b>{{ item.total }}</b></td></tr>
            {% empty %}
            <tr><td colspan="2">Нет данных</td></tr>
            {% endfor %}
        </table>
    </div>
    
    <div class="stat-card" style="flex: 1; min-width: 300px;">
        <h3>✍️ Публикации по авторам</h3>
        <table class="stat-table">
            <tr><th>Автор</th><th>Количество постов</th></tr>
            {% for item in by_author %}
            <tr><td>{{ item.author__fio|default:item.author__username }}</td><td><b>{{ item.total }}</b></td></tr>
            {% empty %}
            <tr><td colspan="2">Нет данных</td></tr>
            {% endfor %}
        </table>
    </div>
</div>

<div class="stat-card">
    <h3>🧮 Матрица: Авторы - Группы</h3>
    <table class="stat-table" style="text-align: center;">
        <tr>
            <th style="text-align: left;">Автор \ Группа</th>
            {% for chat in chats %}
            <th style="text-align: center;">{{ chat.internal_name }}</th>
            {% endfor %}
        </tr>
        {% for row in matrix %}
        <tr>
            <td style="text-align: left;"><b>{{ row.author }}</b></td>
            {% for count in row.counts %}
            <td style="text-align: center;">{{ count }}</td>
            {% endfor %}
        </tr>
        {% empty %}
        <tr><td>Нет данных для матрицы</td></tr>
        {% endfor %}
    </table>
</div>
{% endblock %}
"""