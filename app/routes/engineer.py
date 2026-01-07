import os
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app
from sqlalchemy import text
from app import db
from app.utils import engineer_required
# 导入需要手动触发的任务函数
from app.tasks import update_reservation_status, check_overdue_records

bp = Blueprint('engineer', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """工程模式专用隐蔽登录口"""
    if session.get('is_engineer'):
        return redirect(url_for('engineer.dashboard'))

    if request.method == 'POST':
        key = request.form.get('access_key')
        # 校验环境变量中的 ENGINEER_ACCESS_KEY
        if key == current_app.config.get('ENGINEER_ACCESS_KEY'):
            session['is_engineer'] = True
            session.permanent = False  # 工程模式建议不持久化Session，关闭浏览器即失效
            flash('工程模式认证通过', 'success')
            return redirect(url_for('engineer.dashboard'))
        else:
            flash('认证失败：无效的访问密钥', 'danger')

    return render_template('engineer/login.html')


@bp.route('/logout')
def logout():
    session.pop('is_engineer', None)
    flash('已退出工程模式', 'info')
    return redirect(url_for('main.index'))


@bp.route('/dashboard')
@engineer_required
def dashboard():
    """工程模式主控制台"""
    return render_template('engineer/dashboard.html')


@bp.route('/sql', methods=['POST'])
@engineer_required
def sql_console():
    """只读 SQL 控制台"""
    sql = request.form.get('sql', '').strip()
    result = None
    error = None

    if sql:
        # 安全检查：仅允许 SELECT 语句
        if not sql.lower().startswith('select'):
            error = "安全警告：工程模式仅允许执行 SELECT 查询语句！"
        else:
            try:
                # 使用 SQLAlchemy 执行原生 SQL
                with db.engine.connect() as conn:
                    result_proxy = conn.execute(text(sql))
                    # 获取列名
                    keys = result_proxy.keys()
                    # 获取数据
                    data = result_proxy.fetchall()
                    result = {'keys': keys, 'data': data}
            except Exception as e:
                error = f"SQL 执行错误: {str(e)}"

    return render_template('engineer/dashboard.html', active_tab='sql', sql=sql, result=result, error=error)


@bp.route('/logs')
@engineer_required
def view_logs():
    """实时日志查看器 (读取最后 N 行)"""
    log_path = current_app.config.get('LOG_FILE_PATH')
    lines = []

    if log_path and os.path.exists(log_path):
        try:
            # 【核心修复】：使用 utf-8 读取，并忽略错误 (errors='replace')
            # 这样即使日志文件里有旧的 GBK 乱码，程序也不会报错，而是显示  符号
            # 保证你能看到文件末尾最新的正确日志
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()

            # 读取最后 200 行
            lines = all_lines[-200:]
            lines.reverse()  # 最新的在最上面
        except Exception as e:
            lines = [f"读取日志失败: {str(e)}"]
    else:
        lines = [f"日志文件不存在: {log_path or '未配置路径'}"]

    # 通过 AJAX 请求返回部分 HTML 还是直接渲染页面取决于实现，这里简单直接渲染
    return render_template('engineer/dashboard.html', active_tab='logs', logs=lines)


@bp.route('/trigger/<task_name>', methods=['POST'])
@engineer_required
def trigger_task(task_name):
    """手动触发后台任务"""
    try:
        if task_name == 'update_reservation_status':
            update_reservation_status(current_app.app_context())
            flash('任务 [预约状态流转] 已手动触发执行', 'success')
        elif task_name == 'check_overdue':
            check_overdue_records(current_app.app_context())
            flash('任务 [逾期检查] 已手动触发执行', 'success')
        else:
            flash(f'未知任务: {task_name}', 'warning')
    except Exception as e:
        flash(f'任务执行异常: {str(e)}', 'danger')
        current_app.logger.error(f"手动触发任务失败: {e}")

    return redirect(url_for('engineer.dashboard'))