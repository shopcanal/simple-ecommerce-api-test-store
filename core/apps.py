from django.apps import AppConfig
from django.db.models.signals import post_save, post_delete

from core.signals import (
    item_post_save_receiver,
    item_post_delete_receiver,
    order_post_save_receiver,
)


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        import core.signals

        post_save.connect(item_post_save_receiver, sender="core.Item")
        post_save.connect(order_post_save_receiver, sender="core.Order")
        post_delete.connect(item_post_delete_receiver, sender="core.Item")
