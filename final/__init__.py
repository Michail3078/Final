from flask import Flask, render_template, request, redirect, flash, jsonify, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import or_, inspect
from flask_mail import Mail, Message
import random
import string
from api import init_api

app = Flask(__name__)
app.secret_key = '339efe0aee4cb09be4e9676b66b28a8fdd2b0a0aa32088a5d3cc97f9fcedb4e1'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///main.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
manager = LoginManager(app)
manager.login_view = 'login'
mail = Mail(app)


app.config['MAIL_SERVER'] = 'smtp.mail.ru'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'nanmr20@mail.ru'
app.config['MAIL_DEFAULT_SENDER'] = 'nanmr20@mail.ru'
app.config['MAIL_PASSWORD'] = 'QSw64566BYbLtJwKtlCq'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Поля для 2FA
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(10), nullable=True)
    # Дополнительные поля профиля
    full_name = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(500), nullable=True)
    avatar = db.Column(db.String(500), nullable=True)

    def __init__(self, username, password, email=None, admin=False):
        self.username = username
        self.password = password
        self.email = email
        self.admin = admin

    def __str__(self):
        return f"ID: {self.id}, Логин: {self.username}"


# Модель для хранения кодов 2FA
class TwoFactorCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref=db.backref('two_factor_codes', lazy=True))


# Модель товара
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    category_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    brand = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(500), nullable=False)
    specs = db.Column(db.String(500))
    rating = db.Column(db.Float, default=4.0)
    stock = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, name, category, category_name, price, brand, image, specs, rating=4.0, stock=10):
        self.name = name
        self.category = category
        self.category_name = category_name
        self.price = price
        self.brand = brand
        self.image = image
        self.specs = specs
        self.rating = rating
        self.stock = stock


# Модель корзины
class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('cart_items', lazy=True))
    product = db.relationship('Product', backref=db.backref('cart_items', lazy=True))


# Модель заказа
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Integer, nullable=False)
    delivery_method = db.Column(db.String(100), nullable=False)
    delivery_price = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='Ожидает обработки')
    address = db.Column(db.String(500))
    phone = db.Column(db.String(20))

    user = db.relationship('User', backref=db.backref('orders', lazy=True))


# Модель товаров в заказе
class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    order = db.relationship('Order', backref=db.backref('order_items', lazy=True))


@manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


# Функция для генерации 6-значного кода
def generate_2fa_code():
    return ''.join(random.choices(string.digits, k=6))


# Функция для отправки кода на email
def send_2fa_code(email, code):
    try:
        msg = Message(
            subject="Код подтверждения для входа - PC Components Store",
            recipients=[email],
            body=f"""
Здравствуйте!

Ваш код для двухфакторной аутентификации: {code}

Этот код действителен в течение 5 минут.

Если вы не пытались войти в аккаунт, просто проигнорируйте это письмо.

С уважением,
PC Components Store
            """
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False


# Функция для обновления существующей базы данных
def update_database():
    inspector = inspect(db.engine)

    if 'user' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('user')]
        if 'created_at' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE user ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP'))
                conn.commit()
        if 'email' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE user ADD COLUMN email VARCHAR(120)'))
                conn.commit()
        if 'two_factor_enabled' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE user ADD COLUMN two_factor_enabled BOOLEAN DEFAULT 0'))
                conn.commit()
        if 'two_factor_secret' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE user ADD COLUMN two_factor_secret VARCHAR(10)'))
                conn.commit()
        # Добавляем новые поля для профиля
        if 'full_name' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE user ADD COLUMN full_name VARCHAR(200)'))
                conn.commit()
        if 'phone' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE user ADD COLUMN phone VARCHAR(20)'))
                conn.commit()
        if 'address' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE user ADD COLUMN address VARCHAR(500)'))
                conn.commit()
        if 'avatar' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE user ADD COLUMN avatar VARCHAR(500)'))
                conn.commit()

    if 'product' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('product')]
        if 'created_at' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE product ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP'))
                conn.commit()


# Функция для добавления тестовых товаров с рабочими изображениями
def add_sample_products():
    if Product.query.count() == 0:
        sample_products = [
            # Процессоры
            Product("Intel Core i9-13900K", "cpu", "Процессоры", 58990, "Intel",
                    "https://images.unsplash.com/photo-1591799264318-7e6ef8ddb7ea?w=400&h=300&fit=crop",
                    "24 ядра, до 5.8 ГГц, 36MB кэша", 5.0, 15),
            Product("AMD Ryzen 7 7800X3D", "cpu", "Процессоры", 37490, "AMD",
                    "https://images.unsplash.com/photo-1591799264318-7e6ef8ddb7ea?w=400&h=300&fit=crop",
                    "8 ядер, 16 потоков, 3D V-Cache", 5.0, 10),
            Product("Intel Core i5-13600K", "cpu", "Процессоры", 25990, "Intel",
                    "https://images.unsplash.com/photo-1591799264318-7e6ef8ddb7ea?w=400&h=300&fit=crop",
                    "14 ядер, 20 потоков, до 5.1 ГГц", 4.5, 20),

            # Видеокарты
            Product("NVIDIA GeForce RTX 4090", "gpu", "Видеокарты", 189990, "NVIDIA",
                    "https://images.unsplash.com/photo-1591489378430-ef2f4c626b35?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "24GB GDDR6X, 16384 ядер CUDA, DLSS 3", 5.0, 5),
            Product("NVIDIA GeForce RTX 4070 Ti", "gpu", "Видеокарты", 79990, "NVIDIA",
                    "https://images.unsplash.com/photo-1591489378430-ef2f4c626b35?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "12GB GDDR6X, 7680 ядер CUDA", 4.5, 8),
            Product("AMD Radeon RX 7900 XT", "gpu", "Видеокарты", 89990, "AMD",
                    "https://images.unsplash.com/photo-1591489378430-ef2f4c626b35?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "20GB GDDR6, 5376 потоковых процессоров", 4.5, 7),

            # Оперативная память
            Product("Kingston DDR5 32GB", "ram", "Оперативная память", 11990, "Kingston",
                    "https://images.unsplash.com/photo-1562976540-1502c2145186?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "6400MHz, RGB подсветка, 2x16GB", 4.5, 25),
            Product("Corsair Vengeance 16GB", "ram", "Оперативная память", 5490, "Corsair",
                    "https://images.unsplash.com/photo-1562976540-1502c2145186?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "5200MHz, низкий профиль", 4.0, 30),

            # Накопители
            Product("Samsung 990 Pro 1TB", "storage", "Накопители SSD/HDD", 9990, "Samsung",
                    "https://images.unsplash.com/photo-1597138804456-e7dca7f59d54?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "NVMe PCIe 4.0, чтение 7450 МБ/с", 5.0, 12),
            Product("WD Black SN850X 2TB", "storage", "Накопители SSD/HDD", 15990, "Western Digital",
                    "https://images.unsplash.com/photo-1597138804456-e7dca7f59d54?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "NVMe PCIe 4.0, чтение 7300 МБ/с", 4.5, 8),

            # Материнские платы
            Product("ASUS ROG Maximus Z790", "mb", "Материнские платы", 45990, "ASUS",
                    "https://images.unsplash.com/photo-1523655223303-4e9ef5234587?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "LGA 1700, DDR5, PCIe 5.0, WiFi 6E", 5.0, 6),
            Product("MSI B650 Tomahawk", "mb", "Материнские платы", 18990, "MSI",
                    "https://images.unsplash.com/photo-1523655223303-4e9ef5234587?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "AM5, DDR5, PCIe 4.0", 4.5, 10),

            # Блоки питания
            Product("Corsair RM850x", "psu", "Блоки питания", 13990, "Corsair",
                    "https://images.unsplash.com/photo-1726988372992-cf29696738b4?q=80&w=871&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "850W, 80 Plus Gold, полностью модульный", 5.0, 15),

            # Охлаждение
            Product("Noctua NH-D15", "cooler", "Охлаждение", 8990, "Noctua",
                    "https://images.unsplash.com/photo-1556559343-8594f8854d52?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "Воздушное, 2 вентилятора, тихое", 5.0, 12),
            Product("Arctic Liquid Freezer II 360", "cooler", "Охлаждение", 11990, "Arctic",
                    "https://images.unsplash.com/photo-1556559343-8594f8854d52?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    "Жидкостное, 360mm радиатор, 3 вентилятора", 4.5, 8)
        ]

        for product in sample_products:
            db.session.add(product)
        db.session.commit()
        print("Добавлены тестовые товары с рабочими изображениями")


@app.route('/')
def index():
    popular_products = Product.query.order_by(Product.rating.desc()).limit(8).all()
    return render_template("index.html", products=popular_products)


@app.route('/login', methods=["POST", "GET"])
def login():
    if request.method == "GET":
        if current_user.is_authenticated:
            flash("Вы уже авторизованы", 'warning')
            return redirect("/")
        return render_template("login.html")

    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()

    if user is None:
        flash('Такого пользователя не существует', 'danger')
        return redirect("/login")

    if check_password_hash(user.password, password):
        # Проверяем, включена ли 2FA
        if user.two_factor_enabled and user.email:
            # Генерируем и отправляем код
            code = generate_2fa_code()

            # Сохраняем код в сессию
            session['2fa_user_id'] = user.id
            session['2fa_code'] = code
            session['2fa_expires'] = datetime.now().timestamp() + 300  # 5 минут

            # Сохраняем код в БД
            two_factor_code = TwoFactorCode(
                user_id=user.id,
                code=code,
                expires_at=datetime.now().replace(microsecond=0) + __import__('datetime').timedelta(minutes=5)
            )
            db.session.add(two_factor_code)
            db.session.commit()

            # Отправляем код на email
            if send_2fa_code(user.email, code):
                flash('Код подтверждения отправлен на вашу почту', 'info')
                return redirect(url_for('verify_2fa'))
            else:
                flash('Ошибка отправки кода. Попробуйте позже.', 'danger')
                return redirect("/login")
        else:
            # 2FA не включена, вход сразу
            login_user(user)
            flash(f'Добро пожаловать, {user.username}!', 'success')
            return redirect('/')

    flash("Неверный логин или пароль!", 'danger')
    return render_template("login.html")


@app.route('/verify-2fa', methods=["GET", "POST"])
def verify_2fa():
    """Страница для ввода кода двухфакторной аутентификации"""
    if '2fa_user_id' not in session:
        flash('Сессия истекла, войдите заново', 'danger')
        return redirect('/login')

    if request.method == "GET":
        return render_template("verify_2fa.html")

    code = request.form.get('code')
    user_id = session.get('2fa_user_id')

    # Проверяем код в БД
    two_factor_code = TwoFactorCode.query.filter_by(
        user_id=user_id,
        code=code,
        used=False
    ).filter(TwoFactorCode.expires_at > datetime.now()).first()

    if two_factor_code:
        # Код верный, авторизуем пользователя
        two_factor_code.used = True
        db.session.commit()

        user = User.query.get(user_id)
        login_user(user)

        # Очищаем сессию 2FA
        session.pop('2fa_user_id', None)
        session.pop('2fa_code', None)
        session.pop('2fa_expires', None)

        flash(f'Добро пожаловать, {user.username}!', 'success')
        return redirect('/')
    else:
        flash('Неверный или просроченный код подтверждения', 'danger')
        return render_template("verify_2fa.html")


@app.route('/signin', methods=["POST", "GET"])
def signin():
    if request.method == "GET":
        if current_user.is_authenticated:
            flash("Вы уже авторизованы", 'warning')
            return redirect("/")
        return render_template("signin.html")

    username = request.form.get('username')
    password = request.form.get('password')
    conf_password = request.form.get('conf_password')
    email = request.form.get('email')

    if not (username and password and email):
        flash("Заполните все поля", 'danger')
        return redirect("/signin")

    if password != conf_password:
        flash("Пароли не совпадают", 'danger')
        return redirect("/signin")

    if User.query.filter_by(username=username).first():
        flash("Пользователь с таким логином уже существует", 'danger')
        return redirect("/signin")

    if User.query.filter_by(email=email).first():
        flash("Пользователь с таким email уже существует", 'danger')
        return redirect("/signin")

    hashed_pwd = generate_password_hash(password)
    new_user = User(username=username, password=hashed_pwd, email=email)
    db.session.add(new_user)
    db.session.commit()

    flash("Регистрация прошла успешно! Теперь войдите в аккаунт.", 'success')
    return redirect("/login")


@app.route('/profile', methods=["GET", "POST"])
@login_required
def profile():
    """Страница профиля пользователя"""
    if request.method == "POST":
        action = request.form.get('action')

        if action == 'update_profile':
            # Обновление информации профиля
            full_name = request.form.get('full_name')
            phone = request.form.get('phone')
            address = request.form.get('address')

            if full_name:
                current_user.full_name = full_name
            if phone:
                current_user.phone = phone
            if address:
                current_user.address = address

            db.session.commit()
            flash('Информация профиля обновлена!', 'success')

        elif action == 'change_password':
            # Смена пароля
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not check_password_hash(current_user.password, current_password):
                flash('Текущий пароль неверен', 'danger')
            elif new_password != confirm_password:
                flash('Новый пароль и подтверждение не совпадают', 'danger')
            elif len(new_password) < 6:
                flash('Пароль должен содержать минимум 6 символов', 'danger')
            else:
                current_user.password = generate_password_hash(new_password)
                db.session.commit()
                flash('Пароль успешно изменен!', 'success')

        elif action == 'update_email':
            # Обновление email
            new_email = request.form.get('new_email')
            if new_email:
                if User.query.filter_by(email=new_email).first():
                    flash('Пользователь с таким email уже существует', 'danger')
                else:
                    current_user.email = new_email
                    db.session.commit()
                    flash('Email успешно обновлен!', 'success')

        elif action == 'enable_2fa':
            # Включаем 2FA
            if current_user.email:
                current_user.two_factor_enabled = True
                db.session.commit()
                flash('Двухфакторная аутентификация включена!', 'success')
            else:
                flash('Укажите email для включения 2FA', 'danger')

        elif action == 'disable_2fa':
            # Выключаем 2FA
            current_user.two_factor_enabled = False
            db.session.commit()
            flash('Двухфакторная аутентификация отключена', 'warning')

        return redirect(url_for('profile'))

    # Получаем заказы пользователя
    user_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.order_date.desc()).all()

    return render_template("profile.html", orders=user_orders)


@app.route('/profile/avatar', methods=["POST"])
@login_required
def update_avatar():
    """Обновление аватара пользователя"""
    avatar_url = request.form.get('avatar_url')
    if avatar_url:
        current_user.avatar = avatar_url
        db.session.commit()
        flash('Аватар обновлен!', 'success')
    return redirect(url_for('profile'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Вы вышли из аккаунта", 'info')
    return redirect("/")


@app.route('/catalog')
def catalog():
    # Получаем параметры фильтрации из запроса
    categories = request.args.getlist('category')
    brands = request.args.getlist('brand')
    price_min = request.args.get('price_min', type=int)
    price_max = request.args.get('price_max', type=int)
    sort = request.args.get('sort', 'default')

    # Базовый запрос
    query = Product.query

    # Фильтр по категориям
    if categories:
        query = query.filter(Product.category.in_(categories))

    # Фильтр по брендам
    if brands:
        query = query.filter(Product.brand.in_(brands))

    # Фильтр по цене
    if price_min is not None:
        query = query.filter(Product.price >= price_min)
    if price_max is not None:
        query = query.filter(Product.price <= price_max)

    # Сортировка
    if sort == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Product.price.desc())
    elif sort == 'name_asc':
        query = query.order_by(Product.name.asc())
    elif sort == 'name_desc':
        query = query.order_by(Product.name.desc())
    elif sort == 'rating_desc':
        query = query.order_by(Product.rating.desc())
    else:
        query = query.order_by(Product.id.asc())

    products = query.all()
    return render_template("catalog.html", products=products)


@app.route('/add_to_cart/<int:product_id>')
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)

    # Проверяем, есть ли уже товар в корзине
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()

    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(cart_item)

    db.session.commit()
    flash(f'{product.name} добавлен в корзину', 'success')
    return redirect(request.referrer or '/')


@app.route('/cart')
@login_required
def cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template("cart.html", cart_items=cart_items, total=total)


@app.route('/update_cart/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.user_id != current_user.id:
        flash('Доступ запрещен', 'danger')
        return redirect('/cart')

    action = request.form.get('action')
    if action == 'increase':
        cart_item.quantity += 1
    elif action == 'decrease' and cart_item.quantity > 1:
        cart_item.quantity -= 1
    elif action == 'remove':
        db.session.delete(cart_item)
        db.session.commit()
        flash('Товар удален из корзины', 'info')
        return redirect('/cart')

    db.session.commit()
    flash('Корзина обновлена', 'success')
    return redirect('/cart')


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Корзина пуста', 'warning')
        return redirect('/catalog')

    if request.method == 'GET':
        total = sum(item.product.price * item.quantity for item in cart_items)
        return render_template('checkout.html', cart_items=cart_items, total=total)

    # POST - оформление заказа
    delivery_method = request.form.get('delivery_method')
    delivery_price = int(request.form.get('delivery_price', 0))
    address = request.form.get('address')
    phone = request.form.get('phone')

    total_amount = sum(item.product.price * item.quantity for item in cart_items) + delivery_price

    # Создаем заказ
    order = Order(
        user_id=current_user.id,
        total_amount=total_amount,
        delivery_method=delivery_method,
        delivery_price=delivery_price,
        address=address,
        phone=phone,
        status='Ожидает обработки'
    )
    db.session.add(order)
    db.session.flush()

    # Добавляем товары в заказ
    for item in cart_items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            product_name=item.product.name,
            price=item.product.price,
            quantity=item.quantity
        )
        db.session.add(order_item)

    # Очищаем корзину
    for item in cart_items:
        db.session.delete(item)

    db.session.commit()
    flash('Заказ успешно оформлен! Спасибо за покупку!', 'success')
    return redirect('/')


@app.route('/about')
def about():
    return render_template("about.html")


init_api(app, db, Product)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        update_database()
        add_sample_products()
    app.run(debug=True)