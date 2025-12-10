import atexit  # 导入 atexit

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
# 新增：导入APScheduler和os
from apscheduler.schedulers.background import BackgroundScheduler
import os

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

    # =====================================================================
    # 【修正】APScheduler 定时任务配置 (单个调度器管理所有任务)
    # =====================================================================
    scheduler = None  # 定义一个全局变量来存储调度器实例

    # 仅在非调试模式或主进程中启动调度器
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # 延迟导入任务函数
        from app.tasks import update_reservation_status, print_test_task, check_overdue_records  # 导入所有任务

        # 创建唯一的后台调度器实例
        scheduler = BackgroundScheduler()

        # -------------------- 添加任务1: 更新预约状态 (每小时一次) --------------------
        scheduler.add_job(
            func=update_reservation_status,
            args=[app.app_context()],
            trigger='interval',
            # hours=1,
            # minutes=1,
            seconds=30,
            id='update_reservation_status_task',
            replace_existing=True,
        )
        app.logger.info("已添加任务: update_reservation_status_task")

        # -------------------- 添加任务2: 打印测试 (每5秒一次) --------------------
        # 你可以随时注释掉这部分来停止测试任务
        # scheduler.add_job(
        #     func=print_test_task,
        #     args=[app.app_context()],
        #     trigger='interval',
        #     seconds=5,
        #     id='test_print_task',
        #     replace_existing=True,
        # )
        # app.logger.info("已添加任务: test_print_task")

        # 逾期记录检查任务（新增）
        scheduler.add_job(
            func=check_overdue_records,
            args=[app.app_context()],
            trigger='interval',
            hours=1,  # 和原Timer一样，每24小时执行一次
            id='check_overdue_records_task',
            replace_existing=True,
        )

        # -------------------- 启动调度器 --------------------
        try:
            scheduler.start()
            app.logger.info("APScheduler 调度器已启动。")
        except Exception as e:
            app.logger.error(f"启动 APScheduler 失败: {e}")

    # -------------------- 统一的关闭逻辑 --------------------
    # 使用 atexit 在应用进程退出时关闭调度器
    def shutdown_scheduler():
        if scheduler and scheduler.running:
            app.logger.info("应用正在退出，关闭 APScheduler...")
            scheduler.shutdown()
            app.logger.info("APScheduler 已关闭。")

    atexit.register(shutdown_scheduler)
    # =====================================================================

    return app


# 导入模型
from app import models
