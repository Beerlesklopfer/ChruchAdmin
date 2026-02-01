from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Template filter to access dictionary items by key"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, False)
    return False
