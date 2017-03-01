import functools
import re

from django.core.urlresolvers import reverse
from django.db import models
from django.utils.translation import ugettext_lazy as _

from . import utils as base_utils


class MyManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self._select_related = kwargs.pop('select_related', None)
        self._prefetch_related = kwargs.pop('prefetch_related', None)

        super().__init__(*args, **kwargs)

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)

        if self._select_related:
            qs = qs.select_related(*self._select_related)
        if self._prefetch_related:
            qs = qs.prefetch_related(*self._prefetch_related)

        return qs

    def safe_get(self, *args, **kwargs):
        if len(args) == 1 and 'id' not in kwargs:
            if not args[0]:
                return None
            kwargs['id'] = args[0]
            args = ()
        if 'id' in kwargs and not kwargs.get('id'):
            return None
        try:
            return self.get(*args, **kwargs)
        except self.model.DoesNotExist:
            return None


# noinspection PyProtectedMember
class MyModel(models.Model):
    objects = MyManager()

    class Meta:
        abstract = True

    def get_url(self, **kwargs):
        url = reverse('admin:%s_change' % (self._meta.app_label + '_' + self._meta.model_name,), args=[self.id])
        from base.utils import site_url
        return site_url(url, **kwargs)

    @classmethod
    def get_index_url(cls, **kwargs):
        url = reverse('admin:%s_changelist' % (cls._meta.app_label + '_' + cls._meta.model_name,))
        from base.utils import site_url
        return site_url(url, **kwargs)

    @classmethod
    def f(cls, field_name, many_to_many=None):
        """
        get field
        :return:
        """
        return cls._meta.get_field(field_name, many_to_many)

    @classmethod
    def field_verbose_name(cls, field_name):
        return cls.f(field_name).verbose_name

    @classmethod
    def field_verbose_name(cls, field_name):
        return cls.f(field_name).verbose_name

    @classmethod
    def snake_name(cls):
        from base.utils import un_camel
        return un_camel(cls._meta.model.__name__)

    @classmethod
    def app_label(cls):
        return cls._meta.app_label

    @classmethod
    def model_name(cls):
        return cls._meta.model_name

    @classmethod
    def verbose_name(cls):
        return cls._meta.verbose_name

    @classmethod
    def verbose_name_plural(cls):
        return re.sub('^\d+\. ', '', cls._meta.verbose_name_plural)

    @classmethod
    def has_perm(cls, user, perm: str) -> bool:
        return user.has_perm('%s.%s_%s' % (cls.app_label(), perm, cls.model_name()))

    def call_parent(self, obj, *args, **kwargs):
        """
        Выполнитель родельский метод если он имеется
        """
        return getattr(obj, base_utils.func_name(1), lambda *a, **kwa: None)(*args, **kwargs)


class DateTimeModel(MyModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __getattribute__(self, item):
        if item == 'save_dirty_fields':
            from dirtyfields import DirtyFieldsMixin
            if isinstance(self, DirtyFieldsMixin) and self.is_dirty(check_relationship=True):
                from django.utils import timezone
                self.updated_at = timezone.now()
        return super().__getattribute__(item)


class NameIndexActiveModel(DateTimeModel):
    name = models.CharField(verbose_name='Название', max_length=255)
    index = models.IntegerField(verbose_name='Порядок', default=0)
    active = models.BooleanField(verbose_name=_('active'), default=True)

    class Meta:
        ordering = ['index', 'name']
        abstract = True

    def __str__(self):
        return self.name

    @classmethod
    @functools.lru_cache()
    def all(cls):
        return cls.objects.filter(active=True)

    @classmethod
    def find(cls, object_id):
        for obj in cls.all():
            if obj.id == object_id:
                return obj

    @classmethod
    def next(cls, obj):
        passed = False
        for cur_obj in cls.all():
            if not obj or passed:
                return cur_obj
            if cur_obj == obj:
                passed = True


class IntegerRangeField(models.IntegerField):
    def __init__(self, verbose_name=None, name=None, min_value=None, max_value=None, **kwargs):
        self.min_value, self.max_value = min_value, max_value
        models.IntegerField.__init__(self, verbose_name, name, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'min_value': self.min_value, 'max_value': self.max_value}
        defaults.update(kwargs)
        return super(IntegerRangeField, self).formfield(**defaults)

