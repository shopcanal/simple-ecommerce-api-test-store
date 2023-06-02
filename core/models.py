import os
import requests
from random import randint
from typing import Any, Dict, List
from uuid import uuid4

from django.apps import apps
from django.db.models.signals import post_save
from django.conf import settings
from django.db import models
from django.db.models.options import Options
from django.shortcuts import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django_countries.fields import CountryField
from tenacity import retry, stop_after_attempt, wait_exponential

from core.constants import SHOPCANAL_DEFAULT_HEADERS
from core.signals import raise_response_status


CATEGORY_CHOICES = (("S", "Shirt"), ("SW", "Sport wear"), ("OW", "Outwear"))

LABEL_CHOICES = (("P", "primary"), ("S", "secondary"), ("D", "danger"))

ADDRESS_CHOICES = (
    ("B", "Billing"),
    ("S", "Shipping"),
)

CANAL_WEBHOOK_TOPIC_MODEL: Dict[str, "CanalModel"] = {}


def register_canal_webhook_model(topics: List[str]) -> "CanalModel":
    def decorator(m: "CanalModel") -> "CanalModel":
        for topic in topics:
            CANAL_WEBHOOK_TOPIC_MODEL[topic] = m
        return m

    return decorator


class BaseModel(models.Model):
    """
    Base model that includes default created / updated timestamps.
    """

    id = models.UUIDField(editable=False, primary_key=True, default=uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CanalModel(BaseModel):
    internal_to_canal_mapping: Dict[str, str]
    _meta: Options
    canal_id = models.CharField(null=True, blank=True, max_length=36, db_index=True)

    def transform_to_canal(self) -> Dict[str, Any]:
        canal_json = {}
        for internal_field, canal_field in self.internal_to_canal_mapping.items():
            attributes = internal_field.split("__")
            instance = self
            while len(attributes) > 1:
                instance = getattr(instance, attributes.pop(0))
            final_attribute = attributes.pop(0)
            if isinstance(instance, models.Model):
                field = instance._meta.get_field(final_attribute)
                if isinstance(field, str):
                    value = getattr(instance, field)
                elif isinstance(field, models.ImageField):
                    try:
                        value = getattr(instance, field.name).url
                    except ValueError:
                        value = None
                    # TODO validate that the url is an actual url
                elif isinstance(field, models.Field):
                    value = getattr(instance, field.name)
                else:
                    continue
            else:
                value = getattr(instance, final_attribute)
            if isinstance(canal_field, tuple):
                value = canal_field[0](value)
                canal_field = canal_field[1]
            canal_json[canal_field] = value
        if self.canal_id is not None:
            canal_json["id"] = self.canal_id
        return canal_json

    @classmethod
    def create_or_update_from_canal_json(
        cls, canal_json: Dict[str, Any]
    ) -> "CanalModel":
        ...

    class Meta:
        abstract = True


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stripe_customer_id = models.CharField(max_length=50, blank=True, null=True)
    one_click_purchasing = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


@register_canal_webhook_model(topics=["product/create", "product/update"])
class Item(CanalModel):
    title = models.CharField(max_length=100)
    price = models.FloatField()
    discount_price = models.FloatField(blank=True, null=True)
    category = models.CharField(choices=CATEGORY_CHOICES, max_length=2)
    label = models.CharField(choices=LABEL_CHOICES, max_length=1)
    slug = models.SlugField()
    description = models.TextField()
    image = models.ImageField()
    canal_variant_id = models.CharField(
        blank=True, null=True, max_length=36, unique=True, db_index=True
    )
    added_from_canal = models.BooleanField(default=False)

    internal_to_canal_mapping = {
        "title": "title",
        "description": "body_html",
        "image": "image_src",
    }

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:product", kwargs={"slug": self.slug})

    def get_add_to_cart_url(self):
        return reverse("core:add-to-cart", kwargs={"slug": self.slug})

    def get_remove_from_cart_url(self):
        return reverse("core:remove-from-cart", kwargs={"slug": self.slug})

    def transform_to_canal(self) -> Dict[str, Any]:
        canal_json = super().transform_to_canal()
        canal_json.update(
            {"is_listed": True, "status": "active", "variants": self.variants_json}
        )
        return canal_json

    @property
    def variant_json(self) -> Dict[str, Any]:
        variant_json = {
            "price": str(self.price),
            "title": self.category,
            "option1": self.category,
            "inventory_quantity": 10,
            "inventory_policy": "continue",
        }
        if self.canal_variant_id is not None:
            variant_json["id"] = self.canal_variant_id
        return variant_json

    @property
    def variants_json(self) -> List[Dict[str, Any]]:
        return [self.variant_json]

    @classmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=3),
    )
    def create_or_update_from_canal_json(cls, canal_json: Dict[str, Any]) -> "Item":
        # Only going to push the first variant for now cause this website doesn't support variants
        item, _ = Item.objects.update_or_create(
            canal_id=canal_json["id"],
            defaults={
                "added_from_canal": True,
                "price": float(canal_json["variants"][0]["price"]),
                "canal_variant_id": canal_json["variants"][0]["id"],
                "description": canal_json["body_html"],
                "image": canal_json["image_src"],
                "title": canal_json["title"],
                "slug": canal_json["title"].lower(),
            },
        )
        return item


class OrderItem(CanalModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    internal_to_canal_mapping = {
        "item__canal_variant_id": "variant_id",
        "quantity": "quantity",
    }

    def __str__(self):
        return f"{self.quantity} of {self.item.title}"

    def get_total_item_price(self):
        return self.quantity * self.item.price

    def get_total_discount_item_price(self):
        return self.quantity * self.item.discount_price

    def get_amount_saved(self):
        return self.get_total_item_price() - self.get_total_discount_item_price()

    def get_final_price(self):
        if self.item.discount_price:
            return self.get_total_discount_item_price()
        return self.get_total_item_price()


@register_canal_webhook_model(topics=["order/create", "order/update"])
class Order(CanalModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ref_code = models.CharField(max_length=20, blank=True, null=True)
    items = models.ManyToManyField(OrderItem)
    start_date = models.DateTimeField(auto_now_add=True)
    ordered_date = models.DateTimeField()
    ordered = models.BooleanField(default=False)
    shipping_address = models.ForeignKey(
        "Address",
        related_name="shipping_address",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    billing_address = models.ForeignKey(
        "Address",
        related_name="billing_address",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    payment = models.ForeignKey(
        "Payment", on_delete=models.SET_NULL, blank=True, null=True
    )
    coupon = models.ForeignKey(
        "Coupon", on_delete=models.SET_NULL, blank=True, null=True
    )
    being_delivered = models.BooleanField(default=False)
    received = models.BooleanField(default=False)
    refund_requested = models.BooleanField(default=False)
    refund_granted = models.BooleanField(default=False)

    internal_to_canal_mapping = {}

    """
    1. Item added to cart
    2. Adding a billing address
    (Failed checkout)
    3. Payment
    (Preprocessing, processing, packaging etc.)
    4. Being delivered
    5. Received
    6. Refunds
    """

    def __str__(self):
        return self.user.username

    def get_total(self):
        total = 0
        for order_item in self.items.all():
            total += order_item.get_final_price()
        if self.coupon:
            total -= self.coupon.amount
        return total

    def transform_to_canal(self) -> Dict[str, Any]:
        canal_json = super().transform_to_canal()
        if self.shipping_address is None:
            raise Exception("no shipping address!")
        name = f"{self.shipping_address.user.first_name} {self.shipping_address.user.last_name}"
        canal_json.update(
            {
                "shipping_address": {
                    "name": name.strip() or "Simon Xie",
                    "address1": self.shipping_address.street_address,
                    "city": "San Francisco",  # No city :madge:
                    # All of these are placeholders for now
                    "province": "California",
                    "province_code": "CA",
                    "country": "United States",
                    "country_code": str(self.shipping_address.country),
                    "zip": self.shipping_address.zip,
                    "phone": "8322222222",
                },
                "customer": {
                    "email": "simon.xie@shopcanal.com",
                    "first_name": "Simon",
                    "last_name": "Xie",
                },
            }
        )
        if self.shipping_address.apartment_address:
            canal_json["shipping_address"][
                "address2"
            ] = self.shipping_address.apartment_address
        canal_json["line_items"] = []
        order_item: OrderItem
        for order_item in self.items.all():
            canal_json["line_items"].append(order_item.transform_to_canal())
        return canal_json

    @classmethod
    def create_or_update_from_canal_json(self, canal_json: Dict[str, Any]) -> "Order":
        # Placeholder rn
        user = apps.get_model(*settings.AUTH_USER_MODEL.split(".")).objects.get(
            email="simon.xie@shopcanal.com"
        )
        address = None
        if "shipping_address" in canal_json:
            address, _ = Address.objects.get_or_create(
                street_address=canal_json["shipping_address"]["address1"],
                apartment_address=canal_json["shipping_address"]["address2"] or "",
                country=canal_json["shipping_address"]["country"],
                zip=canal_json["shipping_address"]["zip"],
                address_type="B",
                user=user,
            )
        order, _ = Order.objects.update_or_create(
            canal_id=canal_json["id"],
            defaults={
                "shipping_address": address,
                "ordered_date": timezone.now(),
                "user": user,
                "ordered": True,
            },
        )
        for line_item_json in canal_json["line_items"]:
            order_item, _ = OrderItem.objects.update_or_create(
                canal_id=line_item_json["id"],
                defaults={
                    "item": Item.objects.get(
                        canal_variant_id=line_item_json["variant_id"]
                    ),
                    "ordered": True,
                    "quantity": line_item_json["quantity"],
                    "user": user,
                },
            )
            order.items.add(order_item)
        return order

    def fulfill(self) -> "Fulfillment":
        tracking_number = randint(1000000000, 9999999999)
        fulfillment = Fulfillment.objects.create(
            name="Placeholder Name",
            order=self,
            status="success",
            shipment_status="delivered",
            service="Simon's Fulfillment Serivce",
            tracking_company="UPS",
            tracking_number=str(tracking_number),
            tracking_url=f"https://www.ups.com/track?loc=en_US&tracknum={tracking_number}",
        )
        for order_item in self.items.all():
            FulfillmentLineItem.objects.create(
                fulfillment=fulfillment,
                order_item=order_item,
                quantity=order_item.quantity,
            )
        create_fulfillment_url = os.path.join(
            settings.SHOPCANAL_API_BASE_URL, "fulfillments/"
        )
        response = requests.post(
            create_fulfillment_url,
            json=fulfillment.transform_to_canal(),
            headers=SHOPCANAL_DEFAULT_HEADERS,
        )
        raise_response_status(response)
        fulfillment.canal_id = response.json()["id"]
        fulfillment.save()


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    street_address = models.CharField(max_length=100)
    apartment_address = models.CharField(max_length=100)
    country = CountryField(multiple=False)
    zip = models.CharField(max_length=100)
    address_type = models.CharField(max_length=1, choices=ADDRESS_CHOICES)
    default = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name_plural = "Addresses"


class Payment(models.Model):
    stripe_charge_id = models.CharField(max_length=50)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True
    )
    amount = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username


class Coupon(models.Model):
    code = models.CharField(max_length=15)
    amount = models.FloatField()

    def __str__(self):
        return self.code


class Refund(CanalModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    reason = models.TextField()
    accepted = models.BooleanField(default=False)
    email = models.EmailField()

    def __str__(self):
        return f"{self.pk}"


FULFILLMENT_STATUSES = (
    ("P", "pending"),
    ("O", "open"),
    ("S", "success"),
    ("C", "cancelled"),
    ("E", "error"),
    ("F", "failure"),
)
SHIPMENT_STATUSES = (
    ("confirmed", "confirmed"),
    ("in_transit", "in_transit"),
    ("out_for_delivery", "out_for_delivery"),
    ("delivered", "delivered"),
    ("failure", "failure"),
)


@register_canal_webhook_model(topics=["fulfillment/create", "fulfillment/update"])
class Fulfillment(CanalModel):
    internal_to_canal_mapping = {
        "name": "name",
        "order__canal_id": "order_id",
        "status": "status",
        "shipment_status": "shipment_status",
        "service": "service",
        "tracking_company": "tracking_company",
        "tracking_number": (lambda x: [x], "tracking_numbers"),
        "tracking_url": (lambda x: [x], "tracking_urls"),
    }
    name = models.CharField(max_length=100)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    status = models.CharField(choices=FULFILLMENT_STATUSES, max_length=100)
    shipment_status = models.CharField(
        choices=SHIPMENT_STATUSES, max_length=100, null=True
    )
    service = models.CharField(max_length=100)
    tracking_company = models.CharField(max_length=100)
    tracking_number = models.CharField(max_length=100)
    tracking_url = models.CharField(max_length=500)

    def transform_to_canal(self) -> Dict[str, Any]:
        canal_json = super().transform_to_canal()
        canal_json["line_items"] = []
        for item in self.fulfillmentlineitem_set.all():
            canal_json["line_items"].append(
                {"id": item.order_item.canal_id, "quantity": item.quantity}
            )
        return canal_json

    @classmethod
    def create_or_update_from_canal_json(cls, canal_json: Dict[str, Any]) -> CanalModel:
        f, _ = Fulfillment.objects.update_or_create(
            canal_id=canal_json["id"],
            defaults={
                "name": canal_json["name"],
                "order": Order.objects.get(canal_id=canal_json["order_id"]),
                "status": canal_json["status"],
                "shipment_status": canal_json["shipment_status"],
                "service": canal_json["service"],
                "tracking_company": canal_json["tracking_company"],
                "tracking_number": canal_json["tracking_numbers"][0],
                "tracking_url": canal_json["tracking_urls"][0],
            },
        )
        for line_item_json in canal_json.get("line_items", []):
            order_item = OrderItem.objects.get(canal_id=line_item_json["id"])
            FulfillmentLineItem.objects.update_or_create(
                order_item=order_item,
                fulfillment=f,
                defaults={"quantity": line_item_json["quantity"]},
            )


class FulfillmentLineItem(BaseModel):
    fulfillment = models.ForeignKey(Fulfillment, on_delete=models.CASCADE)
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()


def userprofile_receiver(sender, instance, created, *args, **kwargs):
    if created:
        userprofile = UserProfile.objects.create(user=instance)


post_save.connect(userprofile_receiver, sender=settings.AUTH_USER_MODEL)
