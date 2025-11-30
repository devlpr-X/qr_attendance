# app_core/templatetags/query_string.py
from django import template
from urllib.parse import urlencode

register = template.Library()

@register.simple_tag
def build_url(**kwargs):
    """ ?page=2&search=SW22 гэх мэт query string үүсгэнэ """
    query = {}
    # Одоогийн GET параметрүүдийг авна
    from django.conf import settings
    if hasattr(settings, 'REQUEST') and settings.REQUEST:
        query = settings.REQUEST.GET.copy()
    query.update(kwargs)
    return '?' + urlencode(query) if query else ''