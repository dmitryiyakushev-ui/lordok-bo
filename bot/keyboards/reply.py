"""Reply keyboards (bottom of screen): contact sharing + persistent main menu."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


# ── Main menu button labels (exact-match in F.text filters) ──
MENU_LOG = "📝 Дневник"
MENU_HISTORY = "📋 История"
MENU_REPORT = "📊 Отчёт"
MENU_PATIENTS = "👥 Пациенты"
MENU_SETTINGS = "⚙️ Настройки"
MENU_PREMIUM = "⭐ Премиум"
MENU_FEEDBACK = "💬 Обратная связь"


def request_contact_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard with 'share contact' + manual-entry fallback."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Поделиться номером",
                    request_contact=True,
                )
            ],
            [KeyboardButton(text="✍️ Ввести номер вручную")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def request_location_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for timezone detection via geolocation."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📍 Определить автоматически",
                    request_location=True,
                )
            ],
            [KeyboardButton(text="🕐 Выбрать часовой пояс вручную")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent main menu shown to onboarded users.

    Exact button text must match the MENU_* constants so handlers in
    bot/handlers/menu.py can dispatch correctly.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_LOG), KeyboardButton(text=MENU_HISTORY)],
            [KeyboardButton(text=MENU_REPORT), KeyboardButton(text=MENU_PATIENTS)],
            [KeyboardButton(text=MENU_PREMIUM), KeyboardButton(text=MENU_FEEDBACK)],
            [KeyboardButton(text=MENU_SETTINGS)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите действие или введите команду",
    )


def remove_reply_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
