from rest_framework.routers import DefaultRouter

from apps.ingestion.views import ImportJobViewSet

router = DefaultRouter()
router.register("imports", ImportJobViewSet, basename="importjob")

urlpatterns = router.urls
