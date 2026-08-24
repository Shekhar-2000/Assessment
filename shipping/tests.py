from decimal import Decimal
from django.test import TestCase
from .models import Product, Box, Order, OrderItem
from .services import select_box, NoSuitableBoxError

class CartonSelectionTestCase(TestCase):
    def setUp(self):
        """
        Set up reusable Box fixtures of a few sizes.
        """
        self.small_box = Box.objects.create(
            name="Small Box",
            internal_length=Decimal("10.00"),
            internal_width=Decimal("10.00"),
            internal_height=Decimal("10.00"),
            max_weight=Decimal("2.000"),
            cost=Decimal("1.50")
        )
        self.medium_box = Box.objects.create(
            name="Medium Box",
            internal_length=Decimal("20.00"),
            internal_width=Decimal("20.00"),
            internal_height=Decimal("20.00"),
            max_weight=Decimal("5.000"),
            cost=Decimal("3.00")
        )
        self.large_box = Box.objects.create(
            name="Large Box",
            internal_length=Decimal("50.00"),
            internal_width=Decimal("50.00"),
            internal_height=Decimal("50.00"),
            max_weight=Decimal("20.000"),
            cost=Decimal("7.50")
        )

    def test_single_product_fits_smallest(self):
        """
        1. A single product that fits the smallest box.
        """
        product = Product.objects.create(
            name="Tiny Item",
            sku="SKU-TINY",
            length=Decimal("5.00"),
            width=Decimal("5.00"),
            height=Decimal("5.00"),
            weight=Decimal("0.500")
        )
        order = Order.objects.create(recipient_name="John Doe", shipping_address="123 Main St")
        OrderItem.objects.create(order=order, product=product, quantity=1)

        recommended = select_box(order)
        self.assertEqual(recommended, self.small_box)

    def test_order_needing_largest_box(self):
        """
        2. An order needing the largest available box (fits dimensions and weight of large box).
        """
        product = Product.objects.create(
            name="Large Item",
            sku="SKU-LARGE",
            length=Decimal("30.00"),
            width=Decimal("30.00"),
            height=Decimal("30.00"),
            weight=Decimal("12.000")
        )
        order = Order.objects.create(recipient_name="Jane Doe", shipping_address="456 Oak Ave")
        OrderItem.objects.create(order=order, product=product, quantity=1)

        recommended = select_box(order)
        self.assertEqual(recommended, self.large_box)

    def test_no_box_fits_dimensions(self):
        """
        3a. An order where no box fits because product dimensions are too large.
        """
        product = Product.objects.create(
            name="Gargantuan Item",
            sku="SKU-GARG",
            length=Decimal("60.00"),  # Exceeds large box's 50cm limit
            width=Decimal("10.00"),
            height=Decimal("10.00"),
            weight=Decimal("1.000")
        )
        order = Order.objects.create(recipient_name="Alice Smith", shipping_address="789 Pine Rd")
        OrderItem.objects.create(order=order, product=product, quantity=1)

        with self.assertRaises(NoSuitableBoxError):
            select_box(order)

    def test_no_box_fits_weight(self):
        """
        3b. An order where no box fits because total weight exceeds capacity.
        """
        product = Product.objects.create(
            name="Lead Cube",
            sku="SKU-LEAD",
            length=Decimal("5.00"),
            width=Decimal("5.00"),
            height=Decimal("5.00"),
            weight=Decimal("35.000")  # Exceeds large box's 20kg limit
        )
        order = Order.objects.create(recipient_name="Bob Jones", shipping_address="101 Maple Dr")
        OrderItem.objects.create(order=order, product=product, quantity=1)

        with self.assertRaises(NoSuitableBoxError):
            select_box(order)

    def test_multiple_products_largest_drives_choice(self):
        """
        4. Multiple different products in one order, where the largest one drives the box choice.
           Product A fits in small box, but Product B requires medium box.
        """
        product_a = Product.objects.create(
            name="Small Keychain",
            sku="SKU-KEY",
            length=Decimal("2.00"),
            width=Decimal("2.00"),
            height=Decimal("1.00"),
            weight=Decimal("0.100")
        )
        product_b = Product.objects.create(
            name="Medium Book",
            sku="SKU-BOOK",
            length=Decimal("15.00"),
            width=Decimal("12.00"),
            height=Decimal("3.00"),
            weight=Decimal("1.500")
        )
        order = Order.objects.create(recipient_name="Charlie Brown", shipping_address="202 Cedar Ln")
        OrderItem.objects.create(order=order, product=product_a, quantity=1)
        OrderItem.objects.create(order=order, product=product_b, quantity=1)

        recommended = select_box(order)
        self.assertEqual(recommended, self.medium_box)

    def test_exact_boundary_fit(self):
        """
        5. A product whose dimensions exactly equal a box's internal dimensions (boundary case).
           A 10x10x10 cm product weighing 2.0 kg fits exactly in the Small Box.
        """
        product = Product.objects.create(
            name="Exact Cube",
            sku="SKU-EXACT",
            length=Decimal("10.00"),
            width=Decimal("10.00"),
            height=Decimal("10.00"),
            weight=Decimal("2.000")
        )
        order = Order.objects.create(recipient_name="Delta Ray", shipping_address="303 Elm St")
        OrderItem.objects.create(order=order, product=product, quantity=1)

        recommended = select_box(order)
        self.assertEqual(recommended, self.small_box)

    def test_zero_items_raises_error(self):
        """
        6. An order with zero items raises a NoSuitableBoxError.
        """
        order = Order.objects.create(recipient_name="Echo Vance", shipping_address="404 Ghost Way")
        # No OrderItems created

        with self.assertRaises(NoSuitableBoxError):
            select_box(order)


class RecommendBoxAPITestCase(TestCase):
    def setUp(self):
        self.small_box = Box.objects.create(
            name="Small Box",
            internal_length=Decimal("10.00"),
            internal_width=Decimal("10.00"),
            internal_height=Decimal("10.00"),
            max_weight=Decimal("2.000"),
            cost=Decimal("1.50")
        )
        self.product = Product.objects.create(
            name="Tiny Item",
            sku="SKU-TINY",
            length=Decimal("5.00"),
            width=Decimal("5.00"),
            height=Decimal("5.00"),
            weight=Decimal("0.500")
        )

    def test_api_recommend_box_success(self):
        order = Order.objects.create(recipient_name="John Doe", shipping_address="123 Main St")
        OrderItem.objects.create(order=order, product=self.product, quantity=1)

        response = self.client.post(f"/orders/{order.id}/recommend-box/")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["id"], self.small_box.id)
        self.assertEqual(data["name"], "Small Box")
        self.assertEqual(data["cost"], "1.50")

        # Verify the recommended box was persisted to the database
        order.refresh_from_db()
        self.assertEqual(order.recommended_box, self.small_box)

    def test_api_recommend_box_not_found(self):
        response = self.client.post("/orders/99999/recommend-box/")
        self.assertEqual(response.status_code, 404)

    def test_api_recommend_box_no_fit(self):
        # Empty order has no items, so calling select_box will raise NoSuitableBoxError
        order = Order.objects.create(recipient_name="Echo Vance", shipping_address="404 Ghost Way")
        
        response = self.client.post(f"/orders/{order.id}/recommend-box/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

