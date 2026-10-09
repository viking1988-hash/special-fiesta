"""Optional failure-only alert. Never includes command output, records or secrets."""
import json
import os
import sys
import urllib.request


def main():
    if os.environ.get("CLIENT_BACKUP_ALERTS_ENABLED") != "true":
        print("CLIENT_BACKUP_ALERT_NOT_CONFIGURED", file=sys.stderr)
        return
    token = os.environ.get("CLIENT_BACKUP_TELEGRAM_TOKEN", "")
    chat = os.environ.get("CLIENT_BACKUP_TELEGRAM_CHAT_ID", "")
    # Strict bot token/chat shapes prevent URL/header injection.
    import re
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token) or not re.fullmatch(r"-?\d+", chat):
        raise ValueError("alert credentials")
    test_alert = os.environ.get("CLIENT_BACKUP_TEST_ALERT") == "YES"
    if test_alert and os.environ.get("SYNTHETIC_REHEARSAL_ONLY") != "YES":
        raise ValueError("test isolation required")
    text = ("ТЕСТ аварийного уведомления Автохирург CRM Backup. "
            "Искусственная ошибка проверяет доставку; рабочая CRM и копии не изменены."
            if test_alert else
            "Автохирург: отдельное резервирование клиентов завершилось ошибкой. "
            "Проверьте crm-clients-yandex-backup. Существующие копии не удалены.")
    payload = json.dumps({"chat_id": chat, "text": text}).encode()
    # No redirect handler: never forward the bot token to a redirect destination.
    from yandex import NoRedirect
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request("https://api.telegram.org/bot" + token + "/sendMessage",
                                     data=payload, headers={"Content-Type": "application/json"})
    with opener.open(request, timeout=15) as response:
        result = json.loads(response.read(65536))
        if not result.get("ok"):
            raise ValueError("alert rejected")
        if test_alert:
            message = result.get("result", {})
            message_id = message.get("message_id")
            if type(message_id) is not int or message_id <= 0 or message.get("chat", {}).get("id") != int(chat):
                raise ValueError("delivery evidence missing")
            print("CLIENT_BACKUP_TEST_ALERT_ACCEPTED message_id=" + str(message_id), file=sys.stderr)
    print("CLIENT_BACKUP_ALERT_SENT", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("CLIENT_BACKUP_ALERT_FAILED", file=sys.stderr)
        sys.exit(1)
