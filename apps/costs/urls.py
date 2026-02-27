from django.urls import path

from apps.costs.views import AzurePriceSyncView, AWSPriceSyncView, GCPPriceSyncView, InstanceCompareView

urlpatterns = [
    path("sync/azure/", AzurePriceSyncView.as_view(), name="sync-azure-prices"),
    path("sync/aws/", AWSPriceSyncView.as_view(), name="sync-aws-prices"),
    path("sync/gcp/", GCPPriceSyncView.as_view(), name="sync-gcp-prices"),
    path("instance-compare/", InstanceCompareView.as_view(), name="instance-compare"),
]

