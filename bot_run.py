import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.filters import Command
from dotenv import load_dotenv
import os
from tools.steamapi import SteamAPI  # Импортируем твой класс SteamAPI
from tools.escape import escape_markdown_v2

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Загружаем токен Telegram из .env
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения. Проверьте ваш .env файл.")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()  # Создаем роутер для обработки событий

# Инициализация SteamAPI
steam_api = SteamAPI()

# Обработчик команды /start
@router.message(Command("start"))
async def send_welcome(message):
    await message.answer(
        "Привет! Я бот для поиска игр и пользователей в Steam.\n"
        "Введите название игры или @username для поиска пользователя в инлайн-режиме."
    )

# Обработчик инлайн-запросов
@router.inline_query()
async def inline_query(inline_query: InlineQuery):
    query_text = inline_query.query.strip()
    if not query_text:
        await inline_query.answer([])
        return

    try:
        if query_text.startswith("@"):  # Поиск пользователя
            username = query_text[1:].strip()
            user_info = await steam_api.search_user_by_name(username)

            if "error" in user_info:
                results = [
                    InlineQueryResultArticle(
                        id="no_user",
                        title="Пользователь не найден",
                        input_message_content=InputTextMessageContent(
                            message_text="Пользователь не найден."
                        )
                    )
                ]
            else:
                escaped_name = escape_markdown_v2(user_info["personaname"])
                escaped_description = escape_markdown_v2(user_info.get("description", ""))
                escaped_profile_url = escape_markdown_v2(user_info["profileurl"])
                escaped_datetime = escape_markdown_v2(user_info["account_creation_date"])

                results = [
                    InlineQueryResultArticle(
                        id=user_info["steamid"],
                        title=user_info["personaname"],
                        description=f"SteamID: {user_info['steamid']}",
                        thumbnail_url=user_info["avatar"],
                        input_message_content=InputTextMessageContent(
                            message_text=(
                                f"***Имя:*** `{escaped_name}`\n"
                                f"***Реальное имя:*** `{escaped_description}`\n"
                                f"***Дата создания аккаунта:*** `{escaped_datetime}`\n"
                                f"***STEAM ID:*** `{user_info['steamid']}`\n\n"
                                f"_*[Ссылка на аватарку]({user_info['avatar']})*_\n"
                                f"_*[Ссылка на профиль]({escaped_profile_url})*_"
                            ), parse_mode='MarkdownV2'
                        )
                    )
                ]

        else:  # Поиск игры
            games_info = await steam_api.search_game_by_name(query_text)
            if not games_info:
                results = [
                    InlineQueryResultArticle(
                        id="no_results",
                        title="Игры не найдены",
                        input_message_content=InputTextMessageContent(
                            message_text="По вашему запросу ничего не найдено."
                        )
                    )
                ]
            else:
                results = []
                for i, game_info in enumerate(games_info):
                    appid = game_info['appid']
                    name = escape_markdown_v2(game_info['name'])
                    developers = escape_markdown_v2(', '.join(game_info['developers']))

                    unique_id = f"{appid}_{i}"
                    results.append(
                        InlineQueryResultArticle(
                            id=unique_id,
                            title=name,
                            description=f"Разработчики: {developers}",
                            input_message_content=InputTextMessageContent(
                                message_text=f"***Название:*** `{name}`\n***Разработчики:*** `{developers}`\n\n*_[Ссылка на игру](https://store.steampowered.com/app/{appid})_*", parse_mode="MarkdownV2"
                            )
                        )
                    )

        await inline_query.answer(results, cache_time=300)

    except Exception as e:
        logging.error(f"Ошибка при обработке инлайн-запроса: {e}")
        await inline_query.answer([
            InlineQueryResultArticle(
                id="error",
                title="Ошибка",
                input_message_content=InputTextMessageContent(
                    message_text="Произошла ошибка при обработке запроса. Попробуйте снова."
                )
            )
        ], cache_time=1)


# Регистрируем роутер в диспетчере
dp.include_router(router)

# Запуск бота
if __name__ == '__main__':
    dp.run_polling(bot)