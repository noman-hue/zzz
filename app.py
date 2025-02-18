from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from functools import wraps
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Better to store in an environment variable

# MongoDB connection
client = MongoClient('mongodb://localhost:27017/')
db = client['car_store']
cars_collection = db['cars']
cart_collection = db['cart']
orders_collection = db['orders']
admin_collection = db['admin']

def init_db():
    if not admin_collection.find_one({"username": "ahmed"}):
        admin_collection.insert_one({"username": "ahmed", "password": "123"})  # Store password securely

@app.route('/')
def home():
    car_list = list(cars_collection.find())

    return render_template('index.html', cars=car_list)

@app.route('/cart')
def cart_page():
    cart_items = list(cart_collection.find())
    total_cost = sum(item['price'] * item['quantity'] for item in cart_items)
    
    # Retrieve user details from the session
    user_name = session.get('user_name')
    user_email = session.get('user_email')
    user_address = session.get('user_address')

    return render_template('cart.html', cart=cart_items, total_cost=total_cost, 
                           user_name=user_name, user_email=user_email, user_address=user_address)

@app.route('/add_to_cart/<string:car_id>', methods=['POST'])
def add_to_cart(car_id):
    try:
        car = cars_collection.find_one({"_id": ObjectId(car_id)})
        if car:
            existing_item = cart_collection.find_one({"car_id": car_id})
            if existing_item:
                cart_collection.update_one({"car_id": car_id}, {"$inc": {"quantity": 1}})
            else:
                cart_collection.insert_one({
                    "car_id": car_id, "name": car['name'], "price": car['price'], "quantity": 1
                })
    except:
        return jsonify({"error": "Invalid car ID"}), 400

    return redirect(url_for('cart_page'))

@app.route('/checkout', methods=['POST'])
def checkout():
    data = request.json
    name, email, address = data.get("userName"), data.get("userEmail"), data.get("userAddress")
    cart_items = list(cart_collection.find())

    if not name or not email or not address or not cart_items:
        return jsonify({"message": "Please enter all details and ensure cart is not empty"}), 400

    total_price = sum(item['price'] * item['quantity'] for item in cart_items)
    
    # Store user details in session for later use
    session['user_name'] = name
    session['user_email'] = email
    session['user_address'] = address
    
    # Insert order data into the database
    orders_collection.insert_one({
        "name": name, "email": email, "address": address, "total_price": total_price, "status": "Pending"
    })
    
    cart_collection.delete_many({})  # Clear the cart after checkout
    return jsonify({"message": "Checkout successful, order placed!"})

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        admin = admin_collection.find_one({"username": username, "password": password})
        if admin:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid credentials")
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    cars = list(cars_collection.find())
    order_list = list(orders_collection.find())
    return render_template('admin.html', cars=cars, orders=order_list)

@app.route('/admin/update_order/<string:order_id>', methods=['POST'])
@admin_required
def update_order(order_id):
    try:
        new_status = request.form.get('status')
        orders_collection.update_one({"_id": ObjectId(order_id)}, {"$set": {"status": new_status}})
    except:
        return jsonify({"error": "Invalid order ID"}), 400

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/orders_count')
@admin_required
def orders_count():
    # Query the orders collection to get the total number of orders
    total_orders = orders_collection.count_documents({})
    
    # Optionally, you can also list the orders if needed
    order_list = list(orders_collection.find())
    
    return render_template('orders_count.html', total_orders=total_orders, orders=order_list)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
