from django.urls import path

from apps.inventories.views import InventorySyncView, UserInventoryView

urlpatterns = [
    path("", UserInventoryView.as_view(), name="inventory-list"),
    path("sync/", InventorySyncView.as_view(), name="inventory-sync"),
]
