from django.urls import path

from apps.inventories.views import UserInventoryView

urlpatterns = [
    path("", UserInventoryView.as_view(), name="inventory-list"),
]
