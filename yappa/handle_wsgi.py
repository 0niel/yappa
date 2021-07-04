import json
import os
from importlib import import_module
from pathlib import Path

import httpx
import yaml

DEFAULT_CONFIG_FILENAME = "yappa.yaml"


# TODO after yappa in pip - maybe move load_config to utils and DEFAULT_CONFIG_FILENAME to settings

def load_config(file=DEFAULT_CONFIG_FILENAME):
    """
    TODO is type checking necessary?
    """
    if isinstance(file, str) or isinstance(file, Path):
        with open(file, "r") as f:
            return yaml.load(f.read())
    return yaml.load(file.read())


def load_app(import_path=None, django_settings_module=None):
    # TODO add delay, test if setup is done during setup, not when handling
    #  response
    if import_path:
        *submodules, app_name = import_path.split(".")
        module = import_module(".".join(submodules))
        app = getattr(module, app_name)
        return app
    if django_settings_module:
        from django.core.wsgi import get_wsgi_application
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", django_settings_module)
        import django
        if django.VERSION[0] <= 1 and django.VERSION[1] < 7:
            # call django.setup only for django <1.7.0
            # (because setup already in get_wsgi_application since that)
            # https://github.com/django/django/commit
            # /80d74097b4bd7186ad99b6d41d0ed90347a39b21
            django.setup()
        return get_wsgi_application()
    raise ValueError("either 'import_path' or 'django_settings_module'"
                     "params must be provided")


def patch_response(response):
    """
    returns Http response in the format of
    {
     'status code': 200,
     'body': body,
     'headers': {}
    }
    """
    return {
        'statusCode': response.status_code,
        'headers': dict(response.headers),
        'body': response.content.decode(),
        'isBase64Encoded': False,
    }


def call_app(app, event):
    """
    call wsgi app
    see https://cloud.yandex.ru/docs/functions/concepts/function-invoke#response
    """
    with httpx.Client(app=app,
                      base_url="http://host.url", ) as client:  # TODO where do i find host url???
        request = client.build_request(
            method=event["httpMethod"],
            url=event["url"],
            headers=event["headers"],
            params=event["queryStringParameters"],
            content=json.dumps(event["body"]).encode(),
        )
        response = client.send(request)
        return response


def handle(event, context):
    config = load_config()
    app = load_app(config.get("entrypoint"),
                   config.get("django_settings_module"))
    response = call_app(app, event)
    if not config["debug"]:
        return patch_response(response)
    # TODO add test if debug is true
    return {
        'statusCode': 200,
        'body': {
            "event": event,
            "response": response,
        },
    }
