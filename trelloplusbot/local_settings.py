DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'trello',
        'USER': 'test',
        'PASSWORD': 'Thi4zei0',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }

}

TELEGRAM_BOT_TOKEN = '243570948:AAFRy_hu8PHu_1CtyrKS2X6EeV1sIAUjO6Q'
TELEGRAM_BOT_NAME = 'vladryk_bot'

TRELLO_API_KEY = '8d8bebc6760e08e7fd8f53089bcdfdec'
TRELLO_SECRET_KEY = '651d1f12dd2bb98a89e3e7c0edc75ac3969220f068f290632cd898ace5b09326'

ALLOWED_HOSTS = ['127.0.0.1:8000', '127.0.0.1']