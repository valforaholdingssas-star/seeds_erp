from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.sales.models import ConsolidatedSale, SaleState


@receiver(post_save, sender=ConsolidatedSale)
def queue_invoice_on_active_sale(sender, instance: ConsolidatedSale, **kwargs):
    if instance.state != SaleState.ACTIVE:
        return
    from apps.accounting.services.invoicing import ensure_invoice_for_sale

    ensure_invoice_for_sale(instance)
