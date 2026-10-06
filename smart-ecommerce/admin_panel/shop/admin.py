import csv

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.http import HttpResponse
from django.utils.html import format_html

from .models import (CartItem, Category, Notification, Order, OrderItem, Payment, Product,
                     ProductImage, Role, User)


class RolePermissionMixin:
    """
    Role-based access control for the admin site.
      * admin  -> everything
      * staff  -> only the actions listed in `staff_can` (default: none = hidden)
    """

    staff_can = ("view", "change")

    def _allowed(self, request, action):
        u = request.user
        if not (u.is_active and u.is_staff):
            return False
        if u.role == Role.ADMIN:
            return True
        return action in self.staff_can

    def has_module_permission(self, request):
        return self._allowed(request, "view") or self._allowed(request, "change")

    def has_view_permission(self, request, obj=None):
        return self._allowed(request, "view") or self._allowed(request, "change")

    def has_add_permission(self, request, obj=None):
        return self._allowed(request, "add")

    def has_change_permission(self, request, obj=None):
        return self._allowed(request, "change")

    def has_delete_permission(self, request, obj=None):
        return self._allowed(request, "delete")


# ----------------------------------------------------------------- Users
class UserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "name", "role")

    def clean_password2(self):
        p1, p2 = self.cleaned_data.get("password1"), self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords don't match")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = user.email.lower()
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        help_text='Raw passwords are not stored. <a href="../password/">Change the password</a>.'
    )

    class Meta:
        model = User
        fields = ("email", "name", "role", "is_active")


@admin.register(User)
class UserAdmin(RolePermissionMixin, DjangoUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    list_display = ("email", "name", "role", "auth_provider", "is_active", "date_joined")
    list_filter = ("role", "is_active", "auth_provider")
    search_fields = ("email", "name")
    ordering = ("-date_joined",)
    filter_horizontal = ()
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("name", "role", "auth_provider")}),
        ("Status", {"fields": ("is_active",)}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "name", "role", "password1", "password2")}),)
    readonly_fields = ("auth_provider", "last_login", "date_joined")
    staff_can = ()  # only admins manage users


# -------------------------------------------------------------- Catalogue
@admin.register(Category)
class CategoryAdmin(RolePermissionMixin, admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    staff_can = ("view", "add", "change")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "preview", "position")
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj.pk and obj.image:
            return format_html('<img src="{}" style="height:60px;border-radius:4px">', obj.image.url)
        return "-"


@admin.register(Product)
class ProductAdmin(RolePermissionMixin, admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "stock_flag", "sold_count", "is_active")
    list_filter = ("category", "is_active")
    list_editable = ("price", "stock", "is_active")
    search_fields = ("name", "description")
    inlines = [ProductImageInline]
    staff_can = ("view", "add", "change")  # delete is admin-only

    @admin.display(description="Stock alert")
    def stock_flag(self, obj):
        if obj.stock <= settings.LOW_STOCK_THRESHOLD:
            return format_html('<b style="color:#b91c1c">LOW</b>')
        return "ok"


# ----------------------------------------------------------------- Orders
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ("product_name", "unit_price", "quantity")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False
    fields = ("transaction_id", "amount", "payment_method", "status", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(RolePermissionMixin, admin.ModelAdmin):
    list_display = ("id", "user", "total", "payment_status", "order_status", "created_at")
    list_filter = ("payment_status", "order_status", "created_at")
    list_editable = ("order_status",)
    search_fields = ("id", "user__email", "user__name")
    date_hierarchy = "created_at"
    readonly_fields = ("user", "total", "payment_status", "created_at", "updated_at")
    inlines = [OrderItemInline, PaymentInline]
    actions = ["mark_processing", "mark_shipped", "mark_delivered", "export_selected_csv"]
    staff_can = ("view", "change")

    def _bulk(self, request, queryset, status):
        for order in queryset:  # .save() so signals fire (notification + email)
            order.order_status = status
            order.save()
        self.message_user(request, f"{queryset.count()} order(s) set to {status}.", messages.SUCCESS)

    @admin.action(description="Mark as processing")
    def mark_processing(self, request, qs):
        self._bulk(request, qs, "processing")

    @admin.action(description="Mark as shipped (notifies customer)")
    def mark_shipped(self, request, qs):
        self._bulk(request, qs, "shipped")

    @admin.action(description="Mark as delivered")
    def mark_delivered(self, request, qs):
        self._bulk(request, qs, "delivered")

    @admin.action(description="Export selected to CSV")
    def export_selected_csv(self, request, qs):
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="orders.csv"'
        w = csv.writer(resp)
        w.writerow(["id", "customer", "total", "payment_status", "order_status", "created_at"])
        for o in qs.select_related("user"):
            w.writerow([o.id, o.user.email, o.total, o.payment_status, o.order_status, o.created_at.isoformat()])
        return resp


@admin.register(Payment)
class PaymentAdmin(RolePermissionMixin, admin.ModelAdmin):
    list_display = ("id", "order", "amount", "payment_method", "transaction_id", "status", "created_at")
    list_filter = ("status", "payment_method")
    search_fields = ("transaction_id", "order__id")
    staff_can = ("view",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(RolePermissionMixin, admin.ModelAdmin):
    list_display = ("id", "user", "type", "is_read", "created_at")
    list_filter = ("type", "is_read")
    search_fields = ("user__email", "message")
    staff_can = ()


@admin.register(CartItem)
class CartItemAdmin(RolePermissionMixin, admin.ModelAdmin):
    list_display = ("user", "product", "quantity", "added_at")
    staff_can = ("view",)
