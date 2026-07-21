from __future__ import annotations
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Table, Column, String, Integer, select, DateTime, Float
from marshmallow import ValidationError, validate
from typing import List
from sqlalchemy.exc import IntegrityError
from datetime import datetime

# Initialize the Flask app
app = Flask(__name__)

#MySQL DB configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:<YOUR PASSWORD>@localhost/ecommerce_api'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Create the Base model
class Base(DeclarativeBase):
    pass

# Initialize SQLACHEMY and Marshmallow
db = SQLAlchemy(model_class=Base)
db.init_app(app)
ma = Marshmallow(app)

# Create association table between order and product
order_product = Table(
    "order_product",
    Base.metadata,
    Column("order_id", ForeignKey("orders.id"), primary_key=True),
    Column("product_id", ForeignKey("products.id"), primary_key=True)
)

# Create Database Models
class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    address: Mapped[str] = mapped_column(String(50), nullable = False)
    email: Mapped[str] = mapped_column(String(50), unique=True)
    #One-to-Many relationship : One User --> Many Orders
    orders: Mapped[List["Order"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    #Many-to-One relationship : Many Orders --> One User
    user: Mapped["User"] = relationship(back_populates="orders")
    # Many-to-Many relationship : Order can have multiple products, a product can belong to multiple orders
    products: Mapped[List["Product"]] = relationship("Product", secondary=order_product, back_populates="orders")

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_name: Mapped[str] = mapped_column(String(30), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    # Many-to-Many relationship : Order can have multiple products, a product can belong to multiple orders
    orders: Mapped[List["Order"]] = relationship("Order", secondary=order_product, back_populates="products")

# Define Marshmallow Schemas to serialize and deserialize our models into JSON
# and validate incoming data. 
class UserSchema(ma.SQLAlchemyAutoSchema):             #User Schema
    name=ma.String(
        required=True,
        validate=validate.Length(min=2, max=30))

    email=ma.Email(required=True)

    class Meta:
        model = User
        load_instance = False

class ProductSchema(ma.SQLAlchemyAutoSchema):           #Product Schema
    class Meta:
        model = Product

class OrderSchema(ma.SQLAlchemyAutoSchema):             #Order Schema
    class Meta:
        model = Order
        include_fk = True

    products = ma.Nested(ProductSchema, many=True)

# Initialize the Schemas
user_schema = UserSchema()
users_schema = UserSchema(many=True)
order_schema = OrderSchema()
orders_schema = OrderSchema(many=True)
product_schema = ProductSchema()
products_schema = ProductSchema(many=True)

#=======================USER========================
# Create new uer and prevent duplicate emails
@app.route("/users", methods = ["POST"])
def create_user():
    try:
        user_data = user_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    new_user = User(
    name=user_data['name'],
    address=user_data['address'],
    email=user_data['email']
    )

    db.session.add(new_user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Email already exists"}), 409
    
    return user_schema.jsonify(new_user), 201

# Retrieve all users
@app.route('/users', methods=['GET'])
def get_users():
    query = select(User)
    users = db.session.execute(query).scalars().all()

    return users_schema.jsonify(users), 200

# Retrieve a single user by id
@app.route('/users/<int:id>', methods=['GET'])
def get_user(id):
    user = db.session.get(User, id)

    if not user:
        return jsonify({"message": "User not found"}), 404
    
    return user_schema.jsonify(user), 200

# Update a user by id and prevent duplicate emails
@app.route('/users/<int:id>', methods=['PUT'])
def update_user(id):
    user = db.session.get(User, id)

    if not user:
        return jsonify({"message": "User not found"}), 404
    
    try:
        user_data = user_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    user.name = user_data['name']
    user.address = user_data['address']
    user.email = user_data['email']

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Email already exists"}), 409

    return user_schema.jsonify(user), 200

# Delete a user by id
@app.route('/users/<int:id>', methods=['DELETE'])
def delete_user(id):
    user = db.session.get(User, id)

    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'Successfully deleted user {id}'}), 200

#=======================PRODUCT===============================
# Create a product
@app.route('/products', methods=['POST'])
def create_product():
    try:
        product_data = product_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    new_product = Product(product_name=product_data['product_name'], price=product_data['price'])
    db.session.add(new_product)
    db.session.commit()

    return product_schema.jsonify(new_product), 201

# Retrieve all products and paginate the product listings
@app.route('/products', methods=['GET'])
def get_products():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get('per_page', 5, type=int),10)

    query = db.select(Product)

    pagination = db.paginate(
        query,
        page=page,
        per_page=per_page,
        error_out=False
    )

    return jsonify({
        "products":products_schema.dump(pagination.items),
        "page":pagination.page,
        "per_page":pagination.per_page,
        "total":pagination.total,
        "pages":pagination.pages,
        "has_next":pagination.has_next,
        "has_prev":pagination.has_prev
    }), 200

# Retrieve a single product by id
@app.route('/products/<int:id>', methods=['GET'])
def get_product(id):
    product = db.session.get(Product, id)

    if not product:
        return jsonify({"message": "Product not found"}), 404
    
    return product_schema.jsonify(product), 200

# Update a product by id
@app.route('/products/<int:id>', methods=['PUT'])
def update_product(id):
    product = db.session.get(Product, id)

    if not product:
        return jsonify({"message": "Product not found"}), 404
    
    try:
        product_data = product_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    product.product_name = product_data['product_name']
    product.price = product_data['price']

    db.session.commit()
    return product_schema.jsonify(product), 200

# Delete a product by id
@app.route('/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    product = db.session.get(Product, id)

    if not product:
        return jsonify({'message': 'Product not found'}), 404
    
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': f'Successfully deleted product {id}'}), 200

#============================ORDER=====================================
# Create a new order for a user
@app.route('/orders', methods=['POST'])
def create_order():
    try:
        order_data = order_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    user = db.session.get(User, order_data['user_id'])
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    new_order = Order(user_id=order_data['user_id'])
    db.session.add(new_order)                           
    db.session.commit()

    return order_schema.jsonify(new_order), 201

# Add a product to an order, no duplicates
@app.route('/orders/<int:order_id>/add_product/<int:product_id>', methods=["PUT"])
def add_product_order(order_id, product_id):
    order = db.session.get(Order, order_id)
    
    if not order:
        return jsonify({'message': "Order not found"}), 404
    
    product = db.session.get(Product, product_id)

    if not product:
        return jsonify({'message': "Product not found"}), 404
    
    if product in order.products:
        return jsonify({'message': f"Product {product_id} already in the order"}), 409
    
    order.products.append(product)
    db.session.commit()

    return jsonify({'message': f"Product {product_id} is added to order {order_id}"}), 200

# Retrieve all orders for a user
@app.route('/orders/users/<int:user_id>', methods=['GET'])
def get_user_orders(user_id):
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({'message': f"User {user_id} not found"}), 404
    
    return orders_schema.jsonify(user.orders), 200

# Retrieve all products for an order
@app.route('/orders/<int:order_id>/products', methods=['GET'])
def get_order_products(order_id):
    order = db.session.get(Order, order_id)

    if not order:
        return jsonify({'message': f"Order {order_id} not found"}), 404
    
    return products_schema.jsonify(order.products), 200

# Delete a product from an order
@app.route('/orders/<int:order_id>/remove_product/<int:product_id>', methods=['DELETE'])
def delete_order_product(order_id, product_id):
    order = db.session.get(Order, order_id)
    
    if not order:
        return jsonify({'message': "Order not found"}), 404
    
    product = db.session.get(Product, product_id)

    if not product:
        return jsonify({'message': "Product not found"}), 404
    
    if product not in order.products:
        return jsonify({"message": "Product is not in the order"}), 404
    
    order.products.remove(product)
    db.session.commit()
    return jsonify({'message': f'Successfully deleted product {product_id} from order {order_id}'}), 200


if __name__== "__main__":
    with app.app_context():
        #db.drop_all()
        db.create_all()

    app.run(debug=True)