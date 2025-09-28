import click
from app import create_app, db
from app.models import Record
from app.email import send_overdue_reminder
from threading import Timer

app = create_app()


def check_overdue_records():
    """检查逾期记录并发送提醒邮件"""
    with app.app_context():
        # 获取所有未归还且已逾期的记录
        from datetime import datetime, timedelta
        overdue_records = Record.query.filter(
            Record.status == 'using',
            Record.start_time < datetime.utcnow() - timedelta(days=10)
        ).all()

        for record in overdue_records:
            send_overdue_reminder(record)

    # 每24小时检查一次
    Timer(86400, check_overdue_records).start()


@app.cli.command("init-db")
def init_db():
    """初始化数据库"""
    db.drop_all()
    db.create_all()
    click.echo('数据库已初始化')


@app.cli.command("check-overdue")
def manual_check_overdue():
    """手动检查逾期记录"""
    check_overdue_records()
    click.echo('已检查逾期记录并发送提醒')


if __name__ == '__main__':
    # 启动时开始检查逾期记录
    check_overdue_records()
    app.run(host="0.0.0.0", port=5000, debug=True)  # debug=True仅用于开发
