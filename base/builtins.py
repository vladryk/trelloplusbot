from django import template

register = template.Library()


@register.filter(is_safe=False)
def get_item(dictionary: dict, key):
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)


@register.filter(name='hasattr')
def obj_hasattr(obj: object, key: str):
    return hasattr(obj, key)
