from django.http import request
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from .models import Product, CartItem, Order, OrderItem, OrderStatusHistory
from .cart import Cart
from store import cart
from django.db import transaction


def home(request):
    products = Product.objects.filter(is_available=True)

    return render(request, 'store/home.html', {
        'products': products
    })



def add_to_cart(request, product_id):
    if request.method != 'POST':
        return redirect('home')

    product = get_object_or_404(
        Product,
        id=product_id,
        is_available=True
    )

    cart = Cart(request)
    added = cart.add(product.id)
    print("PRODUCT CLICKED:", product.id, product.name)
    print("SESSION CART:", cart.cart)

    if not added:
        return redirect('cart')

    if request.user.is_authenticated:
        quantity = cart.cart[str(product.id)]['quantity']

        CartItem.objects.update_or_create(
            customer=request.user,
            product=product,
            defaults={'quantity': quantity}
        )

    return redirect('cart')


def cart_view(request):
    cart = Cart(request)

    return render(request, 'store/cart.html', {
        'cart_items': cart.get_items(),
        'total': cart.get_total()
    })


def remove_from_cart(request, product_id):
    if request.method == 'POST':
        cart = Cart(request)
        cart.remove(product_id)

    return redirect('cart')


def update_cart(request, product_id):
    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            return redirect('cart')

        # Allow quantities from 0 to 10 only
        if quantity < 0 or quantity > 10:
            return redirect('cart')

        cart = Cart(request)

        # Update the session cart first
        updated = cart.update_quantity(product_id, quantity)

        # Update the database only if the session update succeeds
        if updated and request.user.is_authenticated:
            if quantity == 0:
                CartItem.objects.filter(
                    customer=request.user,
                    product_id=product_id
                ).delete()
            else:
                CartItem.objects.update_or_create(
                    customer=request.user,
                    product_id=product_id,
                    defaults={'quantity': quantity}
                )

    return redirect('cart')



def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()

    return render(request, 'store/register.html', {
        'form': form
    })

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')

    else:
        form = AuthenticationForm()

    return render(request, 'store/login.html', {'form': form})


def logout_view(request):
    # Save the cart before logging out
    cart_data = request.session.get('cart', {})

    # Log out the user
    logout(request)

    # Restore the cart in the new session
    request.session['cart'] = cart_data
    request.session.modified = True

    return redirect('home')

@login_required(login_url='login')
def account_dashboard(request):
    return render(request, 'store/dashboard.html', {
        'user': request.user
    })



@login_required(login_url='login')

def checkout(request):

    cart = Cart(request)
    cart_items = cart.get_items()

    if not cart_items:
        messages.warning(request, "Your cart is empty.")
        return redirect('cart')

    if request.method == 'POST':

        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        pincode = request.POST.get('pincode', '').strip()

        if not all([full_name, phone, address, city, state, pincode]):
            messages.error(request, "Please fill in all delivery details.")
            return render(request, 'store/checkout.html', {
                'cart_items': cart_items,
                'total': cart.get_total()
            })

        if (
            not phone.isdigit()
            or len(phone) < 10
            or len(phone) > 15
            or not pincode.isdigit()
            or len(pincode) != 6
        ):
            messages.error(request, "Please enter a valid phone number and 6-digit PIN code.")
            return render(request, 'store/checkout.html', {
                'cart_items': cart_items,
                'total': cart.get_total()
            })

        
        # Create the order and its records safely
        with transaction.atomic():
            order = Order.objects.create(
                customer=request.user,
                full_name=full_name,
                phone=phone,
                address=address,
                city=city,
                state=state,
                pincode=pincode,
                total_amount=cart.get_total(),
                payment_method='COD'
            )

            # Save purchased products
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    product_name=item['product'].name,
                    price=item['product'].price,
                    quantity=item['quantity']
                )

            # Save the initial order history
            OrderStatusHistory.objects.create(
                order=order,
                status=order.status,
                note="Order placed successfully",
                changed_by=request.user
            )


        # Save purchased products
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                product_name=item['product'].name,
                price=item['product'].price,
                quantity=item['quantity']
            )

        # Automatically create the first order history record
        OrderStatusHistory.objects.create(
            order=order,
            status=order.status,
            note="Order placed successfully",
            changed_by=request.user
        )


        # Clear session cart
        cart.session['cart'] = {}
        cart.session.modified = True

        # Clear database cart items for this customer
        CartItem.objects.filter(customer=request.user).delete()

        messages.success(request, "Your order has been placed successfully!")
        return redirect('order_history')

    return render(request, 'store/checkout.html', {
        'cart_items': cart_items,
        'total': cart.get_total()
    })


@login_required(login_url='login')
def order_history(request):

    orders = Order.objects.filter(
        customer=request.user
    ).prefetch_related('items')

    return render(request, 'store/order_history.html', {
        'orders': orders
    })


@login_required(login_url='login')
def order_detail(request, order_id):

    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        id=order_id,
        customer=request.user
    )

    return render(request, 'store/order_detail.html', {
        'order': order
    })