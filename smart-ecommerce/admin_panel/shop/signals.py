from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Order
from .notifications import notify_user


@receiver(pre_save, sender=Order)
def remember_old_status(sender, instance, **kwargs):
    instance._old_status = None
    if instance.pk:
        instance._old_status = (
            Order.objects.filter(pk=instance.pk).values_list("order_status", flat=True).first()
        )


@receiver(post_save, sender=Order)
def notify_on_status_change(sender, instance, created, **kwargs):
    old = getattr(instance, "_old_status", None)
    if created or old is None or old == instance.order_status:
        return
    label = instance.get_order_status_display().lower()
    notify_user(
        instance.user,
        "order_status",
        f"Your order #{instance.pk} is now {label}.",
        subject=f"Order #{instance.pk}: {label}",
    )
