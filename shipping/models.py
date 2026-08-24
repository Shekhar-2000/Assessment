from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator


def can_pack_items_3d(box_dims, items):
    """
    Heuristic 3D bin packing algorithm.
    box_dims: tuple of (length, width, height) as Decimals.
    items: list of tuples of (length, width, height) as Decimals.
    Returns True if all items can fit inside the box under 3D rotation, False otherwise.
    Uses a 3D Binary Space Partitioning (BSP) / Guillotine space-splitting heuristic.
    """
    # Sort items by volume descending to pack the largest/most restrictive items first
    sorted_items = sorted(items, key=lambda x: x[0] * x[1] * x[2], reverse=True)
    
    # Track remaining usable spaces in the box. Each space is (x, y, z, dx, dy, dz)
    spaces = [(Decimal('0.0'), Decimal('0.0'), Decimal('0.0'), box_dims[0], box_dims[1], box_dims[2])]
    
    for item_dims in sorted_items:
        space_idx = -1
        chosen_rot = None
        
        # 6 possible rotations of the 3D rectangular box/item
        rotations = list(set([
            (item_dims[0], item_dims[1], item_dims[2]),
            (item_dims[0], item_dims[2], item_dims[1]),
            (item_dims[1], item_dims[0], item_dims[2]),
            (item_dims[1], item_dims[2], item_dims[0]),
            (item_dims[2], item_dims[0], item_dims[1]),
            (item_dims[2], item_dims[1], item_dims[0]),
        ]))
        
        # Find the first space that fits any of the rotations
        for i, space in enumerate(spaces):
            _, _, _, sdx, sdy, sdz = space
            for rot in rotations:
                rx, ry, rz = rot
                if rx <= sdx and ry <= sdy and rz <= sdz:
                    space_idx = i
                    chosen_rot = rot
                    break
            if space_idx != -1:
                break
                
        if space_idx == -1:
            # Item cannot fit in any available partition
            return False
            
        # Place the item and split the space
        sx, sy, sz, sdx, sdy, sdz = spaces.pop(space_idx)
        rx, ry, rz = chosen_rot
        
        # Partition the remaining volume into 3 non-overlapping subspaces
        if sdx > rx:
            spaces.append((sx + rx, sy, sz, sdx - rx, ry, rz))
        if sdy > ry:
            spaces.append((sx, sy + ry, sz, sdx, sdy - ry, rz))
        if sdz > rz:
            spaces.append((sx, sy, sz + rz, sdx, sdy, sdz - rz))
            
    return True


class Product(models.Model):
    """
    Represents a physical item available for purchase.
    Stores physical dimensions (length, width, height in cm) and weight (in kg) 
    to facilitate automated box packing recommendation algorithms.
    """
    name = models.CharField(
        max_length=255, 
        help_text="The name of the product."
    )
    sku = models.CharField(
        max_length=100, 
        unique=True, 
        help_text="Unique Stock Keeping Unit (SKU) identifier."
    )
    length = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="External product length in centimeters (cm)."
    )
    width = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="External product width in centimeters (cm)."
    )
    height = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="External product height in centimeters (cm)."
    )
    weight = models.DecimalField(
        max_digits=8, 
        decimal_places=3, 
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text="Product weight in kilograms (kg), precise to the nearest gram."
    )

    @property
    def volume(self):
        """Calculates the physical volume of the product in cubic centimeters (cm³)."""
        return self.length * self.width * self.height

    def __str__(self):
        return f"{self.name} ({self.sku})"


class Box(models.Model):
    """
    Represents a physical container used for shipping orders.
    Contains internal dimensions, maximum weight limit, and unit cost.
    """
    name = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Unique name or code identifying the box size (e.g., 'Medium Flat Rate Box')."
    )
    internal_length = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Internal usable length of the box in centimeters (cm)."
    )
    internal_width = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Internal usable width of the box in centimeters (cm)."
    )
    internal_height = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Internal usable height of the box in centimeters (cm)."
    )
    max_weight = models.DecimalField(
        max_digits=8, 
        decimal_places=3, 
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text="Maximum weight capacity this box can safely support in kilograms (kg)."
    )
    cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Unit cost of the box in the currency of choice (e.g., 2.50)."
    )

    @property
    def volume(self):
        """Calculates the internal volume of the box in cubic centimeters (cm³)."""
        return self.internal_length * self.internal_width * self.internal_height

    class Meta:
        verbose_name_plural = "Boxes"

    def __str__(self):
        return f"{self.name} ({self.internal_length}x{self.internal_width}x{self.internal_height} cm)"


class Order(models.Model):
    """
    Represents a customer order containing one or more products.
    Stores metadata and links to the recommended box determined by the packaging logic.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the order was placed."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the order was last modified."
    )
    recipient_name = models.CharField(
        max_length=255,
        help_text="Name of the person receiving the shipment."
    )
    shipping_address = models.TextField(
        help_text="Full destination shipping address."
    )
    products = models.ManyToManyField(
        Product, 
        through='OrderItem',
        related_name='orders',
        help_text="Products included in this order (associated through OrderItem with quantities)."
    )
    recommended_box = models.ForeignKey(
        Box, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='orders',
        help_text="The suggested shipping box for this order, populated by the box recommendation engine."
    )

    def find_cheapest_suitable_box(self):
        """
        Finds the cheapest Box that can accommodate all items in this Order.
        Applies a tiered checking process to maximize execution speed and accuracy:
        1. Weight capacity check
        2. Total cumulative volume check (fast pre-filter)
        3. Individual item dimensions bounds check (fast orientation-sorted check)
        4. Multi-item 3D packing heuristic simulation
        """
        items = list(self.items.select_related('product'))
        if not items:
            return None

        # Pre-calculate aggregate weight, volume, and compile list of item dimensions
        total_weight = Decimal('0.000')
        total_volume = Decimal('0.00')
        flat_items_list = []

        for item in items:
            prod = item.product
            qty = item.quantity
            total_weight += prod.weight * qty
            total_volume += prod.volume * qty
            for _ in range(qty):
                flat_items_list.append((prod.length, prod.width, prod.height))

        # Query boxes sorted by price ascending (so the first one that fits is cheapest)
        candidate_boxes = Box.objects.all().order_by('cost')

        for box in candidate_boxes:
            # Tier 1: Weight limit check
            if total_weight > box.max_weight:
                continue

            # Tier 2: Total volume check (if total volume exceeds container, it's impossible to fit)
            if total_volume > box.volume:
                continue

            # Tier 3: Individual item dimension check
            # Ensure every item fits individually within the box (ignoring multi-item stacking for a moment)
            box_dims_sorted = sorted([box.internal_length, box.internal_width, box.internal_height])
            item_too_large = False
            for dims in flat_items_list:
                item_dims_sorted = sorted(dims)
                if (item_dims_sorted[0] > box_dims_sorted[0] or
                    item_dims_sorted[1] > box_dims_sorted[1] or
                    item_dims_sorted[2] > box_dims_sorted[2]):
                    item_too_large = True
                    break
            if item_too_large:
                continue

            # Tier 4: Simulate 3D Packing
            box_dims = (box.internal_length, box.internal_width, box.internal_height)
            if can_pack_items_3d(box_dims, flat_items_list):
                return box

        return None

    def __str__(self):
        return f"Order #{self.id} for {self.recipient_name}"


class OrderItem(models.Model):
    """
    A intermediate (join) model representing a specific product and quantity within an order.
    Defines the Many-to-Many relationship between Orders and Products.
    """
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.PROTECT,
        related_name='order_items'
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Quantity of this product in the order (must be 1 or more)."
    )

    class Meta:
        unique_together = ('order', 'product')

    def __str__(self):
        return f"{self.quantity}x {self.product.name} in Order #{self.order.id}"
