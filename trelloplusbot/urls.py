from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse

from bot import views as bot_views
from bot.models import Token
from .admin import init_admin

init_admin()


def home(request):
    if settings.DEBUG:
        return HttpResponseRedirect(reverse('admin:index'))
    html = '<html><body>{}</body></html>'.format('Trello Plus bot')
    return HttpResponse(html)


def get_token(request, **kwargs):
    token = request.GET.get('token')
    from bot.utils import bot_url
    if token:
        t = Token.objects.create(token=token)
        return HttpResponseRedirect(bot_url('token:%d' % t.id))
    context = dict(
        url=bot_url(),
    )
    return TemplateResponse(request, 'bot/token.html', context)


urlpatterns = [
    url(r'^$', home),
    url(r'^grappelli/', include('grappelli.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^bot/(?P<token_hash>[0-9a-z]+)/$', bot_views.BotRequestView.as_view(), name='bot_webhook'),
    url(r'^token/$', get_token, name='token'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    import debug_toolbar

    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ]
