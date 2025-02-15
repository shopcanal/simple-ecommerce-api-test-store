import os
import requests
from requests.models import Response
from typing import Any, Type, TYPE_CHECKING, Callable

from django.apps import apps
from django.conf import settings

from core.constants import SHOPCANAL_DEFAULT_HEADERS

if TYPE_CHECKING:
    from core.models import Item, Order


def try_catch_wrapper(f: Callable) -> Any:
    def decorator(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except Exception:
            pass

    return decorator


@try_catch_wrapper
def raise_response_status(response: Response):
    try:
        response.raise_for_status()
    except Exception as e:
        print(response.text)
        print(response.json())
        raise type(e)(response.text) from e


@try_catch_wrapper
def item_post_save_receiver(
    sender: Type["Item"], instance: "Item", created: bool, **kwargs: Any
) -> None:
    if instance.added_from_canal:
        return
    if instance.canal_id is None:
        # POST /products/
        create_product_url = os.path.join(settings.SHOPCANAL_API_BASE_URL, "products/")
        response = requests.post(
            create_product_url,
            json=instance.transform_to_canal(),
            headers=SHOPCANAL_DEFAULT_HEADERS,
        )
        raise_response_status(response)
        Item = apps.get_model("core", "Item")
        response_json = response.json()
        Item.objects.filter(id=instance.id).update(
            canal_id=response_json["id"],
            canal_variant_id=response_json["variants"][0]["id"],
        )
    else:
        # PUT /products/{id}
        update_product_url = (
            os.path.join(
                settings.SHOPCANAL_API_BASE_URL, "products", str(instance.canal_id)
            )
            + "/"
        )
        response = requests.put(
            update_product_url,
            json=instance.transform_to_canal(),
            headers=SHOPCANAL_DEFAULT_HEADERS,
        )
        raise_response_status(response)
        if instance.canal_variant_id is not None:
            # PUT /variants/{id}
            variant_json = instance.variant_json
            update_variant_url = (
                os.path.join(
                    settings.SHOPCANAL_API_BASE_URL,
                    "variants",
                    str(instance.canal_variant_id),
                )
                + "/"
            )
            response = requests.put(
                update_variant_url, json=variant_json, headers=SHOPCANAL_DEFAULT_HEADERS
            )
            raise_response_status(response)


@try_catch_wrapper
def item_post_delete_receiver(
    sender: Type["Item"], instance: "Item", **kwargs: Any
) -> None:
    if instance.canal_id is None:
        return
    # DELETE /variants/{id}
    delete_product_url = (
        os.path.join(
            settings.SHOPCANAL_API_BASE_URL, "products", str(instance.canal_id)
        )
        + "/"
    )
    response = requests.delete(delete_product_url, headers=SHOPCANAL_DEFAULT_HEADERS)
    raise_response_status(response)


@try_catch_wrapper
def order_post_save_receiver(
    sender: Type["Order"], instance: "Order", created: bool, **kwargs: Any
) -> None:
    if not instance.ordered:
        return
    if instance.canal_id is None:
        # POST /orders/
        create_order_url = os.path.join(settings.SHOPCANAL_API_BASE_URL, "orders/")
        response = requests.post(
            create_order_url,
            json=instance.transform_to_canal(),
            headers=SHOPCANAL_DEFAULT_HEADERS,
        )
        raise_response_status(response)
        response_json = response.json()
        Order = apps.get_model("core", "Order")
        Order.objects.filter(id=instance.id).update(canal_id=response_json["id"])
        for line_item in response.json()["line_items"]:
            instance.items.all().filter(
                item__canal_variant_id=line_item["variant_id"]
            ).update(canal_id=line_item["id"])

    # update orders isn't supported
    # else:
    #     # PUT /orders/{id}/
    #     update_order_url = (
    #         os.path.join(settings.SHOPCANAL_API_BASE_URL, "orders", str(instance.id))
    #         + "/"
    #     )
    #     response = requests.put(
    #         update_order_url,
    #         json=instance.transform_to_canal(),
    #         headers=SHOPCANAL_DEFAULT_HEADERS,
    #     )
    #     raise_response_status(response)
