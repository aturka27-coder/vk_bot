import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

# Токен берём из переменной окружения (VK_TOKEN в панели Koyeb)
VK_TOKEN = os.getenv('VK_TOKEN')

# ID администраторов — только числа, без кавычек
ADMIN_IDS = [82334743, 24432572, 21360264]

vk_session = vk_api.VkApi(token=VK_TOKEN)
longpoll = VkLongPoll(vk_session)
vk = vk_session.get_api()


# --- Веб-сервер для health-check (чтобы сервис не засыпал) ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'VK Bot is running')

    def log_message(self, format, *args):
        pass  # отключаем лишние логи веб-сервера


def start_web_server():
    port = int(os.getenv('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()


# --- Логика бота ---
def get_answer(user_id, text: str) -> str:
    t = text.lower().strip()

    # --- Приветствие ---
    if any(w in t for w in ['привет', 'здравствуйте', 'хай', 'добрый день', 'доброе утро', 'добрый вечер']):
        return (
            "Привет! 👋 Я помощник автосервиса.\n\n"
            "Если хотите записаться на ремонт — сейчас запись ведётся по телефонам:\n"
            "• 8 (34241) 3-52-02\n"
            "• 8 919 489-43-54\n\n"
            "Хотите узнать стоимость работ? Задайте вопрос — администратор ответит в ближайшее время.\n\n"
            "Также могу подсказать:\n"
            "- «график» — часы работы\n"
        )

    # --- Стоимость: уведомление всем админам ---
    if any(w in t for w in ['стоимость', 'сколько стоит', 'цена', 'сколько', 'почём', 'по цене']):
        for admin_id in ADMIN_IDS:
            try:
                vk.messages.send(
                    user_id=admin_id,
                    message=(
                        f"🔔 Новый вопрос о стоимости работ.\n\n"
                        f"От пользователя: https://vk.com/id{user_id}\n"
                        f"Сообщение: {text}"
                    ),
                    random_id=0
                )
            except Exception as e:
                # Можно вывести в лог, но не ломаем бота
                print(f"Не удалось отправить уведомление админу {admin_id}: {e}")

        return (
            "Ваш вопрос передан администраторам. Они ответят вам в ближайшее время.\n\n"
            "Если срочно — позвоните:\n"
            "• 8 (34241) 3-52-02\n"
            "• 8 919 489-43-54"
        )

    # --- График ---
    if 'график' in t or 'часы работы' in t or 'когда работаете' in t:
        return "Мы работаем ежедневно с 08:00 до 19:00, ВС с 09:00 до 18:00, обед с 12:00 до 13:00."

    # --- ТО ---
    if 'то' in t and ('что входит' in t or 'что делают' in t or t == 'то'):
        return (
                "В ТО входит:\n"
                "1. Замена масла и масляного фильтра\n"
                "2. Замена воздушного фильтра\n"
                "3. Замена фильтра салона\n"
                "4. Замена топливного фильтра\n"
                "5. Замена свечей зажигания\n"
                "Точный список зависит от пробега и марки авто."
        )

    # --- Запись ---
    if any(w in t for w in ['записаться', 'запись', 'хочу на сервис', 'запишитесь']):
        return (
            "Запись на ремонт по телефонам:\n"
            "• 8 (34241) 3-52-02\n"
            "• 8 919 489-43-54\n\n"
            "Назовите марку авто и что нужно сделать — подберём удобное время."
        )

    # --- Универсальный ответ ---
    return (
        "Я помощник автосервиса.\n\n"
        "Напишите:\n"
        "- «стоимость» — узнать цену работ\n"
        "- «график» — часы работы\n"
        "- «то» — что входит в ТО\n\n"
        "Или позвоните: 8 (34241) 3-52-02, 8 919 489-43-54."
    )


def run_bot():
    """Запуск бота в отдельном потоке."""
    print("Бот запущен… Жду сообщения.")
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            message_text = event.text
            if not message_text:
                continue

            answer = get_answer(user_id, message_text)
            try:
                vk.messages.send(user_id=user_id, message=answer, random_id=0)
            except Exception as e:
                print(f"Ошибка отправки ответа пользователю {user_id}: {e}")


# --- Запуск ---
# Бот в фоновом потоке
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# Веб-сервер в основном потоке (Koyeb ждёт, что он привяжется к PORT)
start_web_server()
