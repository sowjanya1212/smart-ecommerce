import json
from datetime import timedelta

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from . import reports
from .models import Order, OrderItem, Product, Role, User


@staff_member_required(login_url="/admin/login/")
def dashboard(request):
    now = timezone.now()
    paid = Order.objects.filter(payment_status="paid")
    total_sales = paid.aggregate(s=Sum("total"))["s"] or 0

    # Revenue trend, last 30 days (missing days filled with 0)
    start = (now - timedelta(days=29)).date()
    by_day = {
        r["day"]: r
        for r in paid.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(revenue=Sum("total"), orders=Count("id"))
    }
    labels, revenue, orders = [], [], []
    for i in range(30):
        d = start + timedelta(days=i)
        labels.append(d.strftime("%b %d"))
        revenue.append(float(by_day[d]["revenue"]) if d in by_day else 0)
        orders.append(by_day[d]["orders"] if d in by_day else 0)

    top = list(
        OrderItem.objects.filter(order__payment_status="paid")
        .values("product_name")
        .annotate(
            units=Sum("quantity"),
            revenue=Sum(ExpressionWrapper(F("unit_price") * F("quantity"), output_field=DecimalField())),
        )
        .order_by("-units")[:5]
    )
    status_counts = {r["order_status"]: r["n"] for r in Order.objects.values("order_status").annotate(n=Count("id"))}
    low_stock = Product.objects.filter(is_active=True, stock__lte=settings.LOW_STOCK_THRESHOLD).order_by("stock")[:15]

    context = {
        "total_sales": total_sales,
        "orders_count": Order.objects.count(),
        "paid_orders": paid.count(),
        "customers": User.objects.filter(role=Role.CUSTOMER).count(),
        "low_stock": low_stock,
        "low_stock_threshold": settings.LOW_STOCK_THRESHOLD,
        "top_products": top,
        "report_links": reports.REPORTS,
        "chart_data": {
            "labels": labels,
            "revenue": revenue,
            "orders": orders,
            "top_labels": [t["product_name"] for t in top],
            "top_units": [t["units"] for t in top],
            "status_labels": list(status_counts.keys()),
            "status_values": list(status_counts.values()),
        },
    }
    return render(request, "shop/dashboard.html", context)


@staff_member_required(login_url="/admin/login/")
def export_report(request, report, fmt):
    if report not in reports.REPORTS or fmt not in ("csv", "pdf"):
        raise Http404()
    data = reports.build_report(report, settings.LOW_STOCK_THRESHOLD)
    return reports.to_csv(data) if fmt == "csv" else reports.to_pdf(data)
