from decimal import Decimal
from django.db import models
from .models import Box, Order

class NoSuitableBoxError(Exception):
    """Exception raised when no shipping box can accommodate the order's items and weight."""
    pass


def select_box(order):
    """
    Selects the cheapest shipping Box that fits all items in the Order.
    
    The selection process checks:
    1. Weight limit: box.max_weight >= total_weight of all items.
    2. Dimensions limit: The box must be large enough to fit the largest individual
       product in the order along each axis (accounting for 3D rotation).
       
    Args:
        order (Order): The Django Order instance to evaluate.
        
    Returns:
        Box: The cheapest suitable Box instance.
        
    Raises:
        NoSuitableBoxError: If no box satisfies the requirements, or if the order is empty.
    """
    # Fetch all items with their associated products in a single query
    items = list(order.items.select_related('product'))
    if not items:
        raise NoSuitableBoxError("Order has no products.")

    # 1. Sum total weight across all items (quantity * product weight)
    total_weight = sum(item.quantity * item.product.weight for item in items)

    # 2. Find the largest dimension of every product in the order along each axis.
    # To support rotation-invariant fitting, we sort the dimensions of each product.
    # We then track the maximum value found across all products for the smallest, 
    # middle, and largest dimensions.
    max_dim_small = Decimal('0.00')  # Max of the smallest dimensions of all products
    max_dim_med = Decimal('0.00')    # Max of the middle dimensions of all products
    max_dim_large = Decimal('0.00')  # Max of the largest dimensions of all products

    for item in items:
        prod = item.product
        # Sort product dimensions (e.g., [height, width, length] -> [min, med, max])
        sorted_dims = sorted([prod.length, prod.width, prod.height])
        
        max_dim_small = max(max_dim_small, sorted_dims[0])
        max_dim_med = max(max_dim_med, sorted_dims[1])
        max_dim_large = max(max_dim_large, sorted_dims[2])

    # 3. Filter Boxes sorted by cost ascending (first matching box is cheapest)
    candidate_boxes = Box.objects.all().order_by('cost')
    
    for box in candidate_boxes:
        # Check weight capacity constraint
        if box.max_weight < total_weight:
            continue
            
        # Check dimensional fit (sort box dimensions to match rotation comparison)
        sorted_box_dims = sorted([box.internal_length, box.internal_width, box.internal_height])
        
        if (sorted_box_dims[0] >= max_dim_small and
            sorted_box_dims[1] >= max_dim_med and
            sorted_box_dims[2] >= max_dim_large):
            return box

    # 4. If no box fit all criteria, raise an exception
    raise NoSuitableBoxError(
        f"No suitable box found for Order #{order.id}. "
        f"Total weight: {total_weight} kg. "
        f"Max product dimensions required: {max_dim_large}x{max_dim_med}x{max_dim_small} cm."
    )
