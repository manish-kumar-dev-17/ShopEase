from django.contrib import admin
from django import forms
from .models import Product, CartItem, Order, OrderItem, OrderStatusHistory

class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = "__all__"

    def clean_status(self):
        new_status = self.cleaned_data.get("status")
        old_status = self.instance.status

        allowed_transitions = {
            "Pending": ["Processing", "Cancelled"],
            "Processing": ["Shipped", "Cancelled"],
            "Shipped": ["Delivered"],
            "Delivered": [],
            "Cancelled": [],
        }

        if self.instance.pk and new_status != old_status:
            allowed = allowed_transitions.get(old_status, [])

            if new_status not in allowed:
                raise ValidationError(
                    f"Cannot change status from {old_status} to {new_status}."
                )

        return new_status



from django.core.exceptions import ValidationError

# =========================================================
# PRODUCT ADMIN
# =========================================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'price',
        'category',
        'is_available',
        'created_at'
    )

    list_filter = (
        'category',
        'is_available'
    )

    search_fields = (
        'name',
        'category'
    )


# =========================================================
# CART ITEM ADMIN
# =========================================================

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):

    list_display = (
        'customer',
        'product',
        'quantity',
        'total_price',
        'added_at'
    )

    list_filter = (
        'added_at',
    )

    search_fields = (
        'customer__username',
        'product__name'
    )

    readonly_fields = (
        'total_price',
        'added_at'
    )


# =========================================================
# ORDER ITEM INLINE
# =========================================================

class OrderItemInline(admin.TabularInline):

    model = OrderItem
    extra = 0


# =========================================================
# ORDER STATUS HISTORY INLINE
# =========================================================

class OrderStatusHistoryInline(admin.TabularInline):

    model = OrderStatusHistory
    extra = 0

    fields = (
        'status',
        'note',
        'changed_by',
        'changed_at'
    )

    readonly_fields = (
        'status',
        'note',
        'changed_by',
        'changed_at'
    )

    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# =========================================================
# ORDER ADMIN
# =========================================================

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm

    list_display = (
        'id',
        'customer',
        'full_name',
        'total_amount',
        'status',
        'created_at'
    )

    list_filter = (
        'status',
        'created_at'
    )

    search_fields = (
        'full_name',
        'phone',
        'customer__username'
    )

    inlines = [
        OrderItemInline,
        OrderStatusHistoryInline
    ]

    
    readonly_fields = (
        'customer',
        'full_name',
        'phone',
        'address',
        'city',
        'state',
        'pincode',
        'total_amount',
        'payment_method',
        'created_at',
    )


    def save_model(self, request, obj, form, change):

        old_status = None

        if change:
            old_status = Order.objects.get(
                pk=obj.pk
            ).status

        super().save_model(
            request,
            obj,
            form,
            change
        )

        # Create first status history when order is created
        if not change:

            OrderStatusHistory.objects.create(
                order=obj,
                status=obj.status,
                note="Order created",
                changed_by=request.user
            )

        # Create history whenever order status changes
        elif old_status != obj.status:

            OrderStatusHistory.objects.create(
                order=obj,
                status=obj.status,
                note=f"Status changed from {old_status} to {obj.status}",
                changed_by=request.user
            )


# =========================================================
# ORDER STATUS HISTORY ADMIN
# =========================================================

@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):

    list_display = (
        'order',
        'status',
        'changed_by',
        'changed_at'
    )

    list_filter = (
        'status',
        'changed_at'
    )

    search_fields = (
        'order__id',
        'note',
        'changed_by__username'
    )

    readonly_fields = (
        'changed_at',
    )