
class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('cart')

        if cart is None:
            cart = self.session['cart'] = {}

        self.cart = cart

    def add(self, product_id):
        from .models import Product

        try:
            product = Product.objects.get(
                id=product_id,
                is_available=True
            )
        except (Product.DoesNotExist, ValueError, TypeError):
            return False

        product_id = str(product.id)
        current_quantity = self.cart.get(
            product_id, {}
        ).get('quantity', 0)

        if (
            not isinstance(current_quantity, int)
            or isinstance(current_quantity, bool)
            or current_quantity < 0
        ):
            current_quantity = 0

        if current_quantity >= 10:
            return False

        self.cart[product_id] = {
            'quantity': current_quantity + 1
        }

        self.save()
        return True

    def update_quantity(self, product_id, quantity):
        product_id = str(product_id)

        if quantity <= 0:
            self.remove(product_id)
            return True

        if quantity > 10:
            return False

        if product_id in self.cart:
            self.cart[product_id]['quantity'] = quantity
            self.save()
            return True

        return False

    def remove(self, product_id):
        product_id = str(product_id)

        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def save(self):
        self.session['cart'] = self.cart
        self.session.modified = True

    def get_items(self):
        from .models import Product

        items = []

        for product_id, item in self.cart.items():
            try:
                product = Product.objects.get(
                    id=product_id,
                    is_available=True
                )

                if not isinstance(item, dict):
                    continue

                quantity = item.get('quantity', 0)

                if (
                    not isinstance(quantity, int)
                    or isinstance(quantity, bool)
                    or quantity < 1
                    or quantity > 10
                ):
                    continue

                items.append({
                    'product': product,
                    'quantity': quantity,
                    'total_price': product.price * quantity
                })

            except (Product.DoesNotExist, ValueError, TypeError):
                continue

        return items

    def get_total(self):
        return sum(
            item['total_price'] for item in self.get_items()
        )
