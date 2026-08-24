from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Order
from .services import select_box, NoSuitableBoxError

class RecommendBoxView(APIView):
    """
    API view to recommend the cheapest shipping box for a given Order.
    
    POST /orders/<order_id>/recommend-box/
    """
    def post(self, request, order_id):
        # 1. Fetch the order, returning 404 if it does not exist
        order = get_object_or_404(Order, id=order_id)
        
        try:
            # 2. Call the carton recommendation service logic
            recommended_box = select_box(order)
            
            # Persist the recommended box decision to the database
            order.recommended_box = recommended_box
            order.save(update_fields=['recommended_box'])
            
            # 3. Return the box data with status 200 OK
            return Response({
                "id": recommended_box.id,
                "name": recommended_box.name,
                "cost": str(recommended_box.cost)  # Decimal converted to string to preserve exact scale/precision in JSON
            }, status=status.HTTP_200_OK)
            
        except NoSuitableBoxError as exc:
            # 4. Return status 400 Bad Request with a descriptive error message if no box fits
            return Response({
                "error": str(exc)
            }, status=status.HTTP_400_BAD_REQUEST)
