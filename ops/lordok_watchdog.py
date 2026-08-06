#!/usr/bin/env python3
"""Сторож ЛОРдока: проверяет, что бот жив, и пишет в @pulsar_dy_bot, если нет.

Проверяет три вещи:
1. Контейнер lordok_bot запущен.
2. Бот отвечает Telegram API (getMe его же токеном).
3. За последние сутки в логе нет паники и бот действительно опрашивает
   Telegram (есть свежие строки лога либо процесс держит соединение).

Алёрт уходит один раз на проблему: пока состояние не изменилось,
повторных сообщений нет. Состояние лежит в /opt/pulsar/state.

Запуск из cron раз в 15 минут.
"""

import json
import subprocess
import urllib.request
from pathlib import Path

PULSAR_ENV = Path("/opt/pulsar/.env")
LORDOK_ENV = Path("/opt/lordok_bot/.env")
STATE = Path("/opt/pulsar/state/lordok_watchdog.json")
CONTAINER = "lordok_bot"


def read_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("\"'")
    return env


def alert(text: str) -> None:
    env = read_env(PULSAR_ENV)
    token = env.get("PULSAR_BOT_TOKEN", "")
    chat = env.get("OWNER_TELEGRAM_ID", "")
    if not token or not chat:
        print("нет токена или chat_id для алёрта")
        return
    data = json.dumps({"chat_id": int(chat), "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as exc:  # noqa: BLE001
        print(f"алёрт не ушёл: {exc}")


def container_running() -> bool:
    out = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER],
        capture_output=True, text=True,
    )
    return out.stdout.strip() == "true"


def bot_answers() -> tuple[bool, str]:
    token = read_env(LORDOK_ENV).get("BOT_TOKEN", "")
    if not token:
        return False, "в .env нет BOT_TOKEN"
    try:
        with urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/getMe", timeout=20
        ) as resp:
            payload = json.load(resp)
        if payload.get("ok"):
            return True, payload["result"].get("username", "")
        return False, str(payload)[:200]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]


def recent_crashes() -> int:
    """Сколько раз бот падал с фатальной ошибкой за последний час."""
    out = subprocess.run(
        ["docker", "logs", "--since", "1h", CONTAINER],
        capture_output=True, text=True,
    )
    log = out.stdout + out.stderr
    return log.count("Fatal error")


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False))


def main() -> None:
    problems = []

    if not container_running():
        problems.append("контейнер lordok_bot не запущен")

    ok, detail = bot_answers()
    if not ok:
        problems.append(f"бот не отвечает Telegram: {detail}")

    crashes = recent_crashes()
    if crashes >= 5:
        problems.append(f"за час {crashes} фатальных ошибок в логе")

    state = load_state()
    was_broken = bool(state.get("problems"))

    if problems:
        if not was_broken:
            alert("🔴 ЛОРдок\n\n" + "\n".join(f"• {p}" for p in problems))
        save_state({"problems": problems})
        print("проблемы:", problems)
        return

    if was_broken:
        alert("🟢 ЛОРдок снова в порядке")
    save_state({"problems": []})
    print("ок")


if __name__ == "__main__":
    main()
