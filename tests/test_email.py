import os
import sys

# -------------------------------------------------------------------
# 关键修复：将项目根目录添加到系统路径
# 这样即使在 tests 文件夹下运行脚本，也能找到上一级的 app 包
# -------------------------------------------------------------------
# 获取当前脚本绝对路径的目录 (doubao_test_2/tests)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取上一级目录 (doubao_test_2)
project_root = os.path.dirname(current_dir)
# 将根目录插入到系统路径的最前面
sys.path.insert(0, project_root)

from app import create_app, mail
from flask_mail import Message

# 创建应用实例
# 确保这里能读取到 .env 中的配置
app = create_app(os.getenv('FLASK_CONFIG') or 'default')


def test_send():
    print("=" * 50)
    print("开始邮件发送测试...")

    with app.app_context():
        # 1. 打印当前加载的配置，用于核对
        mail_server = app.config.get('MAIL_SERVER')
        mail_port = app.config.get('MAIL_PORT')
        mail_username = app.config.get('MAIL_USERNAME')
        admin_email = app.config.get('FLASKY_ADMIN')
        sender = app.config.get('MAIL_SENDER')

        print(f"SMTP 服务器: {mail_server}:{mail_port}")
        print(f"SMTP 用户名: {mail_username}")
        print(f"发件人 (Sender): {sender}")
        print(f"收件人 (Admin): {admin_email}")

        if not mail_username or not app.config.get('MAIL_PASSWORD'):
            print("\n❌ 错误: 未找到邮箱配置。")
            print("请检查 .env 文件中是否正确设置了 MAIL_USERNAME 和 MAIL_PASSWORD。")
            return

        # 2. 构建消息对象
        msg = Message(
            subject='[测试] 物品管理系统配置测试',
            sender=sender,
            recipients=[admin_email],  # 发送给管理员
            body='你好！\n\n如果你收到了这封邮件，说明你的 Flask 邮件配置 (SMTP) 完全正常。\n\n来自 tests/test_email.py 脚本。'
        )

        # 3. 尝试发送
        try:
            print("\n正在连接 SMTP 服务器发送邮件，请稍候...")
            mail.send(msg)
            print("\n✅ 成功: 邮件已发送！")
            print(f"请检查邮箱 {admin_email} 的收件箱（如果未收到，请检查垃圾邮件箱）。")
        except Exception as e:
            print(f"\n❌ 失败: 发送过程中出现异常。\n错误信息: {e}")
            print("-" * 30)
            print("排查建议：")
            print("1. 确保 MAIL_PASSWORD 是邮箱的【授权码】，而不是登录密码。")
            print("2. QQ邮箱通常使用 端口 465 (SSL) 或 587 (TLS)。当前配置为 587。")
            print("3. 检查是否开启了 VPN，有时会阻断 SMTP 连接。")


if __name__ == '__main__':
    test_send()