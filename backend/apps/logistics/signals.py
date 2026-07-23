from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.sales.models import ConsolidatedSale, SaleState, fulfillment_requires_envia


@receiver(post_save, sender=ConsolidatedSale)
def create_shipment_on_active_sale(sender, instance: ConsolidatedSale, created, **kwargs):
    if instance.state != SaleState.ACTIVE:
        return
    from apps.sales.services.fulfillment import sync_shipment_for_fulfillment

    # Solo ENVIA crea/mantiene envío para guías; DOMICILIO/OFICINA limpia pendientes
    sync_shipment_for_fulfillment(instance)
