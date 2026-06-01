import os
import time
import requests

# ==================== 配置区域（从环境变量读取）====================
USER_LOGIN    = os.environ.get("MC_PANEL_LOGIN", "")
USER_PASSWORD = os.environ.get("MC_PANEL_PASSWORD", "")
TG_CONFIG     = os.environ.get("TG_CONFIG", "")   # 格式: chat_id:bot_token
# ==================================================================

BASE_URL   = "https://www.location-minecraft.com"
LOGIN_URL  = f"{BASE_URL}/connexion.php"
RENEW_URL  = f"{BASE_URL}/.deploy_status_henson.json"

BASE_HEADERS = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "origin": BASE_URL,
    "referer": f"{BASE_URL}/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/109.0.0.0 Safari/537.36"
    )
}

# 使用 requests.Session 自动管理和传递登录成功后的 Cookie
session = requests.Session()

# ──────────────────────────────────────────────
#  Telegram 通知
# ──────────────────────────────────────────────

def _tg_creds():
    if not TG_CONFIG or " " not in TG_CONFIG:
        return None, None
    chat_id, bot_token = TG_CONFIG.split(" ", 1)
    return chat_id.strip(), bot_token.strip()

def _line(char="─", n=28):
    return char * n

def send_telegram(title: str, lines: list[tuple], status: str = "info"):
    icons = {"success": "✅", "error": "❌", "warning": "⚠️", "info": "💬"}
    icon  = icons.get(status, "💬")

    chat_id, bot_token = _tg_creds()
    if not chat_id:
        return

    body_rows = []
    for label, value in lines:
        if label:
            body_rows.append(f"<b>{label}</b>：{value}")
        else:
            body_rows.append(value)

    msg = (
        f"{icon}  <b>Location-MC Panel</b>\n"
        f"<code>{_line()}</code>\n"
        f"<b>{title}</b>\n"
        f"<code>{_line()}</code>\n"
        + "\n".join(body_rows)
    )

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        if resp.status_code != 200:
            print(f"[TG] 发送失败 {resp.status_code}: {resp.text}")
    except requests.exceptions.RequestException as e:
        print(f"[TG] 网络异常: {e}")

# ──────────────────────────────────────────────
#  核心逻辑：登录
# ──────────────────────────────────────────────

def login() -> bool:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] 正在尝试登录面板...")

    # 构造抓包到的标准 Payload 格式
    login_data = {
        "login": USER_LOGIN,
        "passwd": USER_PASSWORD,
        "stay": "0"
    }

    try:
        # 使用连接池发送标准的 form 表单
        resp = session.post(LOGIN_URL, data=login_data, headers=BASE_HEADERS, timeout=15)
        
        # 业务层逻辑判断：密码错误时返回包含 "NOT_FOUND" 相关的提示
        if "NOT_FOUND" in resp.text or resp.status_code != 200:
            send_telegram("登录失败", [
                ("账号", USER_LOGIN),
                ("状态码", str(resp.status_code)),
                ("返回内容", resp.text[:100]),
                ("时间", ts),
            ], "error")
            return False
            
        print("登录请求发送成功（页面已重定向/刷新）。Session Cookie 已在后台记录。")
        return True

    except requests.exceptions.RequestException as e:
        send_telegram("登录网络异常", [
            ("账号", USER_LOGIN),
            ("错误信息", str(e)[:200]),
            ("时间", ts),
        ], "error")
        return False

# ──────────────────────────────────────────────
#  核心逻辑：续期保活
# ──────────────────────────────────────────────

def try_renew() -> bool:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] 正在向 Henson 部署引擎发送续期心跳...")

    try:
        # 带着已登录的 Session Cookie 去 GET 状态文件触发续期
        resp = session.get(RENEW_URL, headers=BASE_HEADERS, timeout=15)
        
        # 判断是否成功返回了包含部署版本的元数据 JSON
        if resp.status_code == 200 and "deployedRevisions" in resp.text:
            print("自动续期心跳发送成功！")
            send_telegram("服务器续期成功 🎉", [
                ("账号", USER_LOGIN),
                ("部署状态", "已刷新 (main)"),
                ("时间", ts),
            ], "success")
            return True
        else:
            send_telegram("续期状态异常", [
                ("账号", USER_LOGIN),
                ("状态码", str(resp.status_code)),
                ("响应内容", resp.text[:150]),
                ("时间", ts),
            ], "warning")
            return False

    except requests.exceptions.RequestException as e:
        send_telegram("续期网络异常", [
            ("账号", USER_LOGIN),
            ("错误原因", str(e)[:200]),
            ("时间", ts),
        ], "error")
        return False

def main():
    print("Location-Minecraft 自动续期脚本启动...")
    if login():
        try_renew()

if __name__ == "__main__":
    main()