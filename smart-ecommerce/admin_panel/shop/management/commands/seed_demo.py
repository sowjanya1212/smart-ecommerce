"""python manage.py seed_demo  -> demo users, catalogue and 30 days of paid orders."""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models import Category, Order, OrderItem, Payment, Product, User

USERS = [
    ("admin@example.com", "Admin User", "admin", "Admin@12345"),
    ("staff@example.com", "Staff User", "staff", "Staff@12345"),
    ("customer@example.com", "Demo Customer", "customer", "Customer@12345"),
    ("alice@example.com", "Alice Johnson", "customer", "Customer@12345"),
    ("bob@example.com", "Bob Smith", "customer", "Customer@12345"),
]
CATALOGUE = {
    "Electronics": [("Wireless Headphones", "Noise-cancelling over-ear headphones.", "89.99", 25),
                    ("Smart Watch", "Fitness tracking and notifications.", "129.00", 12),
                    ("Bluetooth Speaker", "Portable waterproof speaker.", "45.50", 3),
                    ("USB-C Charger 65W", "Fast GaN charger.", "29.99", 40)],
    "Books": [("Clean Code", "A handbook of agile software craftsmanship.", "33.00", 18),
              ("Designing Data-Intensive Apps", "The big ideas behind reliable systems.", "49.90", 4)],
    "Home": [("Ceramic Mug Set", "Set of 4 mugs.", "24.00", 30),
             ("LED Desk Lamp", "Dimmable with USB port.", "36.75", 2),
             ("Yoga Mat", "Non-slip 6mm mat.", "19.99", 22)],
}


class Command(BaseCommand):
    help = "Seed demo data"

    def handle(self, *args, **opts):
        random.seed(42)
        for email, name, role, pw in USERS:
            if not User.objects.filter(email=email).exists():
                User.objects.create_user(email=email, password=pw, name=name, role=role)
        products = []
        for cat_name, items in CATALOGUE.items():
            cat, _ = Category.objects.get_or_create(name=cat_name, defaults={"slug": cat_name.lower()})
            for name, desc, price, stock in items:
                p, _ = Product.objects.get_or_create(
                    name=name, defaults={"category": cat, "description": desc, "price": Decimal(price), "stock": stock})
                products.append(p)

        if not Order.objects.exists():
            customers = list(User.objects.filter(role="customer"))
            for _ in range(40):
                user = random.choice(customers)
                picks = random.sample(products, random.randint(1, 3))
                lines = [(p, random.randint(1, 3)) for p in picks]
                total = sum(p.price * q for p, q in lines)
                order = Order.objects.create(
                    user=user, total=total, payment_status="paid",
                    order_status=random.choice(["processing", "shipped", "delivered", "delivered"]),
                    shipping_address="221B Baker Street, London")
                for p, q in lines:
                    OrderItem.objects.create(order=order, product=p, product_name=p.name, unit_price=p.price, quantity=q)
                    Product.objects.filter(pk=p.pk).update(sold_count=p.sold_count + q)
                    p.sold_count += q
                Payment.objects.create(order=order, amount=total, transaction_id=f"seed_pi_{order.pk}", status="succeeded")
                when = timezone.now() - timedelta(days=random.randint(0, 29), hours=random.randint(0, 23))
                Order.objects.filter(pk=order.pk).update(created_at=when)
        self.stdout.write(self.style.SUCCESS("Demo data ready. Logins: admin@example.com / Admin@12345, "
                                             "staff@example.com / Staff@12345, customer@example.com / Customer@12345"))
