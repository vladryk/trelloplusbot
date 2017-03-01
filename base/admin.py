from collections import defaultdict
from functools import wraps

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.main import EMPTY_CHANGELIST_VALUE
from django.core.exceptions import PermissionDenied
from django.db.models.constants import LOOKUP_SEP
from django.forms import MediaDefiningClass
from django.http import Http404
from django.http import HttpRequest
from django.template import Template, Context
from django.utils.html import format_html, conditional_escape
from django.utils.safestring import mark_safe

from base import utils as base_utils
from base.models import MyModel, DateTimeModel
from bot.models import TgUser

_model_names_cache = defaultdict(str)


def short_description(description):
    """
    Sets 'short_description' attribute (this attribute is used by list_display).
    """

    def decorator(func):
        func.short_description = description
        return func

    return decorator


def order_field(field):
    """
    Sets 'admin_order_field' attribute (this attribute is used by list_display).
    """

    def decorator(func):
        func.admin_order_field = field
        return func

    return decorator


def allow_tags(func):
    """
    Unified 'allow_tags' that works both for list_display and readonly_fields.
    """

    @wraps(func)
    def inner(*args, **kwargs):
        res = func(*args, **kwargs)
        return mark_safe(res)

    inner.allow_tags = True
    return inner


def boolean(func):
    """
    Sets 'boolean' attribute (this attribute is used by list_display).
    """
    func.boolean = True
    return func


def limit_width(max_len):
    """
    Truncates the decorated function's result if it is longer than max_length.
    """

    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            res = func(*args, **kwargs)
            return _truncatechars(res, max_len)

        return inner

    return decorator


def format_output(template_string):
    """
    Formats the value according to template_string using django's Template.
    Example::
        @allow_tags
        @format_output('{{ value|urlize }}')
        def object_url(self, obj):
            return obj.url
    """

    tpl = Template(template_string)

    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            res = func(*args, **kwargs)
            return tpl.render(Context({'value': res}))

        return inner

    return decorator


def apply_filter(filter_string):
    """
    Applies django template filter to output.
    Example::
        @apply_filter('truncatewords:2')
        def object_description(self, obj):
            return obj.description
    """

    def decorator(func):
        template_string = "{{ value|%s }}" % filter_string
        return format_output(template_string)(func)

    return decorator


class MutedHttp404(Http404):
    pass


class MutedPermissionDenied(PermissionDenied):
    pass


def model_names():
    if _model_names_cache:
        return _model_names_cache
    for app in settings.INSTALLED_APPS:
        models = apps.get_app_config(app).get_models()
        for model in models:
            if issubclass(model, MyModel):
                _model_names_cache[model.snake_name()] = model.verbose_name()
    return _model_names_cache


def my_admin_getattr(key, model_admin=None):
    """
    Превращение полей вида self__city__region и self__city__region__link в текстовые значения из связи и со ссылкой на объект.
    """
    if key.startswith('self' + LOOKUP_SEP):
        args = key.split(LOOKUP_SEP)[1:]
        name = args[-1]
        if name == 'link':
            args = args[:-1]
            name = args[-1]

            def f(obj):
                for arg in args:
                    if obj:
                        obj = getattr(obj, arg)
                if not obj:
                    return EMPTY_CHANGELIST_VALUE
                assert isinstance(obj, MyModel), type(obj)
                assert isinstance(model_admin, MyAdmin)
                if not obj.has_perm(model_admin.request.user, 'change'):
                    return str(obj)
                return model_admin.obj2link(obj)
        else:
            def f(obj):
                o = obj
                for arg in args:
                    o = getattr(o, arg)
                return str(o)
        f.short_description = model_names()[name] or name
        f.admin_order_field = LOOKUP_SEP.join(args)
        return f
    raise AttributeError(key)


class MyAdminMeta(MediaDefiningClass):
    def __getattr__(cls, key):
        return my_admin_getattr(key)


class MyAdmin(admin.ModelAdmin, metaclass=MyAdminMeta):
    prepend_fields = []
    postpone_fields = []
    readonly = False
    readonly_if_not_superuser = False
    request = None
    mute_http_404_exception = False
    mute_permission_denied_exception = False
    change_list_template = 'admin/change_list_filter_sidebar.html'

    def __getattr__(self, key):
        return my_admin_getattr(key, self)

    def obj2link(self, obj: MyModel, title='', attr=None, calc_title=None, new_window=False):
        if not obj:
            return ''
        if not title and attr and hasattr(obj, attr):
            title = getattr(obj, attr)
        if not title and callable(calc_title):
            title = calc_title(obj)
        title = title or str(obj)
        if not obj.has_perm(self.request.user, 'change'):
            return title
        return self.show_link(obj.get_url(), title, new_window=new_window)

    @classmethod
    def show_link(cls, url, title, new_window=False):
        target = '_blank' if new_window else '_self'
        return format_html('<a href="{}" target="{}">{}</a>', url, target, conditional_escape(title))

    def get_queryset(self, request: HttpRequest):
        self.request = request
        return super().get_queryset(request)

    def has_add_permission(self, request: HttpRequest):
        if self.readonly_if_not_superuser and not request.user.is_superuser:
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request: HttpRequest, obj=None):
        if self.readonly_if_not_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request: HttpRequest):
        actions = super().get_actions(request)
        if not self.has_delete_permission(request):
            for k in actions:
                if k == 'delete_selected':
                    del actions[k]
                    break
        return actions

    def get_readonly(self, request: HttpRequest, obj=None):
        if self.readonly_if_not_superuser and not request.user.is_superuser:
            return True
        return self.readonly

    def get_prepend_fields(self, request: HttpRequest, obj=None):
        return self.prepend_fields

    def get_postpone_fields(self, request: HttpRequest, obj=None):
        add = []
        if hasattr(self, 'get_links'):
            add.append('links')
        return self.postpone_fields + add

    def get_readonly_fields(self, request: HttpRequest, obj=None):
        if self.get_readonly(request, obj):
            readonly_fields = base_utils.get_field_names(obj.__class__)
        else:
            readonly_fields = list(super().get_readonly_fields(request, obj))
        readonly_fields = self.get_prepend_fields(request, obj) + readonly_fields + self.get_postpone_fields(request, obj)
        if isinstance(obj, DateTimeModel):
            readonly_fields += ['updated_at', 'created_at']
        exclude = self.exclude or []
        return [f for f in readonly_fields if f not in exclude]

    def get_fields(self, request: HttpRequest, obj=None):
        prepend_fields = self.get_prepend_fields(request, obj)
        postpone_fields = self.get_postpone_fields(request, obj)
        return self.get_prepend_fields(request, obj) + [f for f in super().get_fields(request, obj) if f not in prepend_fields and f not in postpone_fields] + postpone_fields

    @short_description('TgUser')
    @order_field('tguser')
    def tguser_link(self, obj):
        return self.obj2link(obj.tguser)

    @short_description('TgUser links')
    def tguser_links(self, obj):
        if not obj.tguser:
            return ''
        assert isinstance(obj.tguser, TgUser)
        return obj.tguser.get_admin_name_advanced(self.request)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except Http404 as e:
            if self.mute_http_404_exception:
                raise MutedHttp404(e)
            raise
        except PermissionDenied as e:
            if self.mute_permission_denied_exception:
                raise MutedPermissionDenied(e)
            raise

    def changelist_view(self, request, extra_context=None):
        try:
            return super().changelist_view(request, extra_context)
        except Http404 as e:
            if self.mute_http_404_exception:
                raise MutedHttp404(e)
            raise
        except PermissionDenied as e:
            if self.mute_permission_denied_exception:
                raise MutedPermissionDenied(e)
            raise

    @short_description('Ссылки')
    @allow_tags
    def links(self, obj: MyModel):
        if not obj.id or not hasattr(self, 'get_links'):
            return ''
        links = self.get_links(obj)
        if not links:
            return ''
        result = []
        for pair in links:
            kwargs = pair[2] if len(pair) == 3 else dict()
            result.append(self.show_link(*pair[:2], **kwargs))
        return '<br/>'.join(result)


class NameIndexActiveAdmin(MyAdmin):
    list_display = ['id', 'name', 'index', 'active']
    list_filter = ['active']
    search_fields = ['id', 'name']

    def get_list_display(self, request):
        list_display = list(super().get_list_display(request))
        for f in ('index', 'active'):
            if f in list_display:
                list_display.remove(f)
                list_display.append(f)
        return list_display


try:
    from django.template.defaultfilters import truncatechars as _truncatechars
except ImportError:  # django < 1.4
    def _truncatechars(string, max_len):
        # simple fallback
        dots = '...'
        assert max_len > len(dots)
        if len(string) < max_len:
            return string
        return string[:(max_len - len(dots))] + dots
