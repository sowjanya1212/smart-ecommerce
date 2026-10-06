"""Report builders + CSV/PDF renderers used by the dashboard export buttons."""
import csv
import io
from datetime import datetime

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse

from .models import Order, OrderItem, Product

REPORTS = {
    "sales": "Sales report",
    "top-products": "Top-selling products",
    "revenue": "Daily revenue",
    "low-stock": "Low stock products",
}


def build_report(name, low_stock_threshold=5):
    if name == "sales":
        rows = [
            [o.id, o.user.email, f"{o.total:.2f}", o.payment_status, o.order_status, o.created_at.strftime("%Y-%m-%d %H:%M")]
            for o in Order.objects.select_related("user").order_by("-created_at")
        ]
        headers = ["Order #", "Customer", "Total", "Payment", "Status", "Created"]
    elif name == "top-products":
        qs = (
            OrderItem.objects.filter(order__payment_status="paid")
            .values("product_name")
            .annotate(
                units=Sum("quantity"),
                revenue=Sum(ExpressionWrapper(F("unit_price") * F("quantity"), output_field=DecimalField())),
            )
            .order_by("-units")
        )
        headers = ["Product", "Units sold", "Revenue"]
        rows = [[r["product_name"], r["units"], f"{r['revenue']:.2f}"] for r in qs]
    elif name == "revenue":
        qs = (
            Order.objects.filter(payment_status="paid")
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(orders=Count("id"), revenue=Sum("total"))
            .order_by("day")
        )
        headers = ["Date", "Orders", "Revenue"]
        rows = [[r["day"].isoformat(), r["orders"], f"{r['revenue']:.2f}"] for r in qs]
    elif name == "low-stock":
        qs = Product.objects.filter(is_active=True, stock__lte=low_stock_threshold).select_related("category").order_by("stock")
        headers = ["Product", "Category", "Stock", "Price"]
        rows = [[p.name, p.category.name if p.category else "-", p.stock, f"{p.price:.2f}"] for p in qs]
    else:
        raise Http404("Unknown report")
    return {"name": name, "title": REPORTS[name], "headers": headers, "rows": rows}


def to_csv(report):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(report["headers"])
    writer.writerows(report["rows"])
    resp = HttpResponse(buf.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{report["name"]}.csv"'
    return resp


def to_pdf(report):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title=report["title"])
    styles = getSampleStyleSheet()
    data = [report["headers"]] + [[str(c) for c in row] for row in report["rows"]] or [report["headers"]]
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    doc.build(
        [
            Paragraph(report["title"], styles["Title"]),
            Paragraph(f"Generated {datetime.now():%Y-%m-%d %H:%M}", styles["Normal"]),
            Spacer(1, 12),
            table,
        ]
    )
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{report["name"]}.pdf"'
    return resp
