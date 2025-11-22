from django.apps import AppConfig


class TrackerConfig(AppConfig):
    name = "tracker"

    def ready(self):
        # import signals to register them
        from . import signals  # noqa: F401