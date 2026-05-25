from rest_framework.routers import DefaultRouter

from apps.orders.views import CustomerViewSet, OrderViewSet

router = DefaultRouter()
router.register("orders", OrderViewSet, basename="order")
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = router.urls
