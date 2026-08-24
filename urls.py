from django.urls import path
from shipping.views import RecommendBoxView

urlpatterns = [
    path('orders/<int:order_id>/recommend-box/', RecommendBoxView.as_view(), name='recommend-box'),
]
