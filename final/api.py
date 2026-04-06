from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request


def init_api(app, db, Product):
    """
    Подключает API в существующее Flask-приложение.
    """

    api_bp = Blueprint("api", __name__, url_prefix="/api")

    def _json_error(message: str, status: int = 400):
        return jsonify({"ok": False, "error": message}), status

    def _product_to_dict(product) -> dict[str, Any]:
        """Преобразует товар в словарь для JSON ответа"""
        return {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "category_name": product.category_name,
            "price": product.price,
            "brand": product.brand,
            "image": product.image,
            "specs": product.specs,
            "rating": product.rating,
            "stock": product.stock,
        }

    @api_bp.get("/products")
    def list_products():
        """
        Получить список товаров с фильтрацией по категориям.

        Query параметры:
        - category: фильтр по категории (можно указать несколько, например ?category=cpu&category=gpu)
        - brand: фильтр по бренду (можно указать несколько)
        - price_min: минимальная цена
        - price_max: максимальная цена
        - sort: сортировка (price_asc, price_desc, name_asc, name_desc, rating_desc)
        - limit: ограничение количества товаров
        """
        query = Product.query

        # Фильтр по категориям
        categories = request.args.getlist('category')
        if categories:
            query = query.filter(Product.category.in_(categories))

        # Фильтр по брендам
        brands = request.args.getlist('brand')
        if brands:
            query = query.filter(Product.brand.in_(brands))

        # Фильтр по цене
        price_min = request.args.get('price_min', type=int)
        if price_min is not None:
            query = query.filter(Product.price >= price_min)

        price_max = request.args.get('price_max', type=int)
        if price_max is not None:
            query = query.filter(Product.price <= price_max)

        # Сортировка
        sort = request.args.get('sort', 'default')
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

        # Ограничение количества
        limit = request.args.get('limit', type=int)
        if limit is not None:
            query = query.limit(limit)

        products = query.all()

        return jsonify({
            "ok": True,
            "count": len(products),
            "items": [_product_to_dict(p) for p in products]
        })

    @api_bp.get("/products/<int:product_id>")
    def get_product(product_id: int):
        """Получить информацию о конкретном товаре"""
        product = db.session.get(Product, product_id)
        if product is None:
            return _json_error("Product not found", 404)
        return jsonify({"ok": True, "item": _product_to_dict(product)})

    @api_bp.get("/categories")
    def get_categories():
        """Получить список всех доступных категорий"""
        from sqlalchemy import func

        categories = db.session.query(
            Product.category,
            Product.category_name,
            func.count(Product.id).label('count')
        ).group_by(Product.category, Product.category_name).all()

        return jsonify({
            "ok": True,
            "categories": [
                {
                    "code": cat.category,
                    "name": cat.category_name,
                    "count": cat.count
                }
                for cat in categories
            ]
        })

    @api_bp.get("/brands")
    def get_brands():
        """Получить список всех брендов"""
        from sqlalchemy import func

        brands = db.session.query(
            Product.brand,
            func.count(Product.id).label('count')
        ).group_by(Product.brand).order_by(Product.brand).all()

        return jsonify({
            "ok": True,
            "brands": [
                {
                    "name": brand.brand,
                    "count": brand.count
                }
                for brand in brands
            ]
        })

    # Регистрируем blueprint в приложении
    app.register_blueprint(api_bp)