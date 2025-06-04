from flask import Flask, redirect, render_template, request, url_for, jsonify, session
import sqlite3
# import bcrypt
import json

app = Flask(__name__)
app.secret_key = 'chuoi_ngau_nhien'  # Change this to a secure random key in production

def get_db_connection():
    conn = sqlite3.connect('bookstore.db')
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def check_admin_auth():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    return None

@app.route("/admin/login", methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM Admins WHERE username = ?', (username,)).fetchone()
        conn.close()
        if admin:
            print('co')

        if admin and password == admin['password_hash']:
        # if admin and bcrypt.checkpw(password.encode('utf-8'), admin['password_hash'].encode('utf-8')):
            session['admin_id'] = admin['admin_id']
            return redirect(url_for('admin_orders'))
        else:
            return render_template('admin_login.html', error='Tên đăng nhập hoặc mật khẩu không đúng')

    return render_template('admin_login.html')

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('admin_login'))

@app.route("/")
def home():
    conn = get_db_connection()
    Books = conn.execute('SELECT * FROM Books').fetchall()
    BusinessBooks = conn.execute('SELECT * FROM Books WHERE category = ?', ('Business',)).fetchall()
    TechnologyBooks = conn.execute('SELECT * FROM Books WHERE category = ?', ('Technology',)).fetchall()
    RomanticBooks = conn.execute('SELECT * FROM Books WHERE category = ?', ('Romantic',)).fetchall()
    AdventureBooks = conn.execute('SELECT * FROM Books WHERE category = ?', ('Adventure',)).fetchall()
    FictionalBooks = conn.execute('SELECT * FROM Books WHERE category = ?', ('Fiction',)).fetchall()
    conn.close()
    return render_template("index.html", books=Books, businessBooks=BusinessBooks,
                           technologyBooks=TechnologyBooks, romanticBooks=RomanticBooks,
                           adventureBooks=AdventureBooks, fictionalBooks=FictionalBooks)

@app.route("/cart")
def cart():
    return render_template("cart.html")

@app.route("/checkout", methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        address = request.form.get('address')
        city = request.form.get('city')
        phone = request.form.get('phone')
        cart_data = request.form.get('cart')

        # Check for missing fields
        if not all([full_name, email, address, city, phone, cart_data]):
            print(f"Missing fields: full_name={full_name}, email={email}, address={address}, city={city}, phone={phone}, cart={cart_data}")
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        try:
            cart = json.loads(cart_data)
            if not isinstance(cart, list) or not cart:
                print("Cart is empty or not a list:", cart_data)
                return jsonify({'success': False, 'error': 'Cart is empty or invalid'}), 400

            # Validate cart items
            for item in cart:
                if not all(key in item for key in ['id', 'price', 'quantity']):
                    print("Invalid cart item:", item)
                    return jsonify({'success': False, 'error': 'Invalid cart item format'}), 400
                if not isinstance(item['price'], (int, float)) or not isinstance(item['quantity'], int) or item['quantity'] <= 0:
                    print("Invalid price or quantity:", item)
                    return jsonify({'success': False, 'error': 'Invalid price or quantity in cart'}), 400

            subtotal = sum(item['price'] * item['quantity'] for item in cart)
            shipping = 5.00 if subtotal > 0 else 0.00
            total_amount = subtotal + shipping
        except (ValueError, KeyError) as e:
            print("Error parsing cart:", str(e), cart_data)
            return jsonify({'success': False, 'error': f'Invalid cart data: {str(e)}'}), 400

        conn = get_db_connection()
        try:
            cursor = conn.execute('''
                INSERT INTO Orders (full_name, email, address, city, phone, total_amount)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (full_name, email, address, city, phone, total_amount))
            order_id = cursor.lastrowid

            for item in cart:
                conn.execute('''
                    INSERT INTO Order_Items (order_id, book_id, quantity, price)
                    VALUES (?, ?, ?, ?)
                ''', (order_id, item['id'], item['quantity'], item['price']))

            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            print("Database error:", str(e))
            return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500
        finally:
            conn.close()

        return jsonify({'success': True})

    return render_template("checkout.html")

@app.route("/book")
def book():
    book_id = request.args.get('book_id')
    if not book_id:
        return "Book ID not provided", 400

    conn = get_db_connection()
    book = conn.execute('SELECT * FROM Books WHERE book_id = ?', (book_id,)).fetchone()
    conn.close()

    if not book:
        return "Book not found", 404

    return render_template("book.html", book=book)

@app.route("/search")
def search():
    q = request.args.get('q')
    conn = get_db_connection()
    book = conn.execute('SELECT * FROM Books WHERE title LIKE ? COLLATE NOCASE', ('%' + q + '%',)).fetchone()
    conn.close()
    if not book:
        return "Book not found", 404
    return render_template("book.html", book=book)

@app.route("/admin/orders")
def admin_orders():
    if check_admin_auth():
        return check_admin_auth()
    conn = get_db_connection()
    orders = conn.execute('SELECT * FROM Orders ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template("admin_orders.html", orders=orders)

@app.route("/admin/books")
def admin_books():
    if check_admin_auth():
        return check_admin_auth()
    conn = get_db_connection()
    books = conn.execute('SELECT * FROM Books').fetchall()
    conn.close()
    return render_template("admin_books.html", books=books)

@app.route("/admin/add_book", methods=['POST'])
def add_book():
    if check_admin_auth():
        return check_admin_auth()
    data = request.get_json()
    title = data.get('title')
    author = data.get('author')
    price = data.get('price')
    category = data.get('category')
    image_url = data.get('image_url')
    description = data.get('description')

    if not all([title, author, price, category, image_url, description]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    try:
        price = float(price)
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid price format'}), 400

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO Books (title, author, price, category, image_url, description)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (title, author, price, category, image_url, description))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route("/admin/delete_book", methods=['POST'])
def delete_book():
    if check_admin_auth():
        return check_admin_auth()
    data = request.get_json()
    book_id = data.get('book_id')

    if not book_id:
        return jsonify({'success': False, 'error': 'Book ID not provided'}), 400

    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM Books WHERE book_id = ?', (book_id,))
    book = cursor.fetchone()
    if not book:
        conn.close()
        return jsonify({'success': False, 'error': 'Book not found'}), 404

    conn.execute('DELETE FROM Books WHERE book_id = ?', (book_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route("/admin/update_order", methods=['POST'])
def update_order():
    if check_admin_auth():
        return check_admin_auth()
    data = request.get_json()
    order_id = data.get('order_id')
    status = data.get('status')

    if not all([order_id, status]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    if status not in ['Pending', 'Completed', 'Cancelled']:
        return jsonify({'success': False, 'error': 'Invalid status'}), 400

    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM Orders WHERE order_id = ?', (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return jsonify({'success': False, 'error': 'Order not found'}), 404

    conn.execute('UPDATE Orders SET status = ? WHERE order_id = ?', (status, order_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

if __name__ == "__main__":
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5000, ssl_context=('cert.pem', 'key.pem'))
