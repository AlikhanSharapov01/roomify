from django.urls import path
from .views import IngestView, KrishaByIdView

urlpatterns = [
    path('krisha/<int:ad_id>',  KrishaByIdView.as_view(), name='krisha-by-id'),
]
