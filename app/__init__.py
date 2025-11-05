from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from config import Config

import pytz

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
mail = Mail()

migrate = Migrate()  # 初始化迁移工具


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)  # 绑定应用和数据库

    # 延迟导入路由，避免循环导入
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    # 【修改1：同时导入 spaces 蓝图和 get_space_hierarchy 函数】
    from app.routes.spaces import bp as spaces_bp, get_space_hierarchy
    app.register_blueprint(spaces_bp, url_prefix='/spaces')

    from app.routes.items import bp as items_bp
    app.register_blueprint(items_bp, url_prefix='/items')

    from app.routes.records import bp as records_bp
    app.register_blueprint(records_bp, url_prefix='/records')

    from app.routes.reservations import bp as reservations_bp
    app.register_blueprint(reservations_bp, url_prefix='/reservations')

    # 新增：注册管理员蓝图（URL前缀为 /admin）
    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # 【新增：将空间层级函数注册为模板全局函数】
    app.jinja_env.globals['get_space_hierarchy'] = get_space_hierarchy

    # 创建数据库表
    with app.app_context():
        db.create_all()

    return app


# 导入模型
from app import models
