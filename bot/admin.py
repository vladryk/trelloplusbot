from bitfield import BitField
from bitfield.forms import BitFieldCheckboxSelectMultiple
from django.contrib import admin

from base import utils as base_utils
from base.admin import MyAdmin
from bot.models import TgUser, TgMessage, TgChat


@admin.register(TgChat)
class TgChatAdmin(MyAdmin):
    list_display = ['id', 'tg_id', 'type', 'title', 'active']
    search_fields = ['tg_id', 'title']
    list_filter = ['active']
    ordering = ['-id']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TgUser)
class TgUserAdmin(MyAdmin):
    list_display = ('id', 'tg_id', 'username', 'first_name', 'last_name', 'active')
    search_fields = ['tg_id', 'first_name', 'last_name', 'username']
    list_filter = ['active']
    readonly_fields = ['last_active_at', 'dialog']
    ordering = ['-id']
    formfield_overrides = {
        BitField: {'widget': BitFieldCheckboxSelectMultiple},
    }

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TgMessage)
class TgMessageAdmin(MyAdmin):
    list_display = ['id', 'tguser_link', 'fnc', 'result', 'text', 'requests_made', 'created_at']
    list_filter = ['chat_type', 'fnc', 'result']
    search_fields = ['tguser__username', 'tguser__first_name', 'tguser__last_name', 'tg_id', 'from_tg_id', 'text', 'message', 'fnc', 'result']
    readonly_fields = base_utils.get_field_names(TgMessage, [])
    prepend_fields = ['tguser_link', 'self__tgchat__link']
    exclude = ['tguser', 'tgchat']
    ordering = ['-id']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request, obj=None):
        return False
