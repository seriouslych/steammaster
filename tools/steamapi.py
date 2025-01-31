import os
from dotenv import load_dotenv
import aiohttp
import pickle
from datetime import datetime, timedelta
from rapidfuzz import process, fuzz  # Быстрый нечеткий поиск
from tqdm import tqdm  # Прогресс-бар

# Загрузка переменных окружения из .env файла
load_dotenv()

class SteamAPI:
    def __init__(self):
        # Получаем API ключ из переменной окружения
        self.api_key = os.getenv("STEAM_API_KEY")
        if not self.api_key:
            raise ValueError("STEAM_API_KEY не найден в переменных окружения. Проверьте ваш .env файл.")
        
        self.base_url = "https://api.steampowered.com"
        self.cache_dir = "tools/cache"
        self.games_cache_file = os.path.join(self.cache_dir, "games_cache.bin")
        self.search_cache_file = os.path.join(self.cache_dir, "search_cache.bin")
        self.cache_expiry = timedelta(weeks=1)  # Кэш действителен 1 неделю
        
        # Создаем папку для кэша, если её нет
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Загружаем список всех игр при инициализации
        self.games_list = None
        self.search_cache = self.load_cache(self.search_cache_file) or {}

    def load_cache(self, cache_file):
        """Загрузить кэш из бинарного файла."""
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)
                if 'timestamp' in cache_data and datetime.now() - cache_data['timestamp'] < self.cache_expiry:
                    return cache_data['data']
        return None

    def save_cache(self, cache_file, data):
        """Сохранить данные в бинарный файл кэша."""
        cache_data = {
            'timestamp': datetime.now(),
            'data': data
        }
        with open(cache_file, 'wb') as f:
            pickle.dump(cache_data, f)

    async def get_all_games(self):
        """Асинхронное получение полного списка игр через ISteamApps/GetAppList."""
        games_list = self.load_cache(self.games_cache_file)
        if games_list:
            return games_list
        
        url = f"{self.base_url}/ISteamApps/GetAppList/v2/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception("Не удалось получить список игр из Steam API.")
                
                data = await response.json()
                games_list = data['applist']['apps']
                
                # Сохраняем список игр в кэш
                self.save_cache(self.games_cache_file, games_list)
                
                return games_list

    async def search_game_by_name(self, game_name):
        """Поиск игры по названию с использованием rapidfuzz и прогресс-бара."""
        if game_name in self.search_cache:
            return self.search_cache[game_name]
        
        if not self.games_list:
            print("Загрузка списка игр...")
            self.games_list = await self.get_all_games()
        
        # Используем rapidfuzz для нечеткого поиска
        print("Поиск совпадений...")
        matches = []
        for game in tqdm(
            self.games_list,
            desc="Фильтрация игр",
            unit="игра",
            leave=False  # Удаляем прогресс-бар после завершения
        ):
            score = fuzz.WRatio(game_name.lower(), game['name'].lower())
            if score >= 50:  # Пропускаем совпадения с низким рейтингом
                matches.append((game['name'], score))
        
        # Ограничиваем количество результатов до 10
        matches = sorted(matches, key=lambda x: x[1], reverse=True)[:10]
        
        found_games = []
        for match, _ in tqdm(
            matches,
            desc="Обработка результатов",
            unit="игра",
            leave=False  # Удаляем прогресс-бар после завершения
        ):
            game = next((g for g in self.games_list if g['name'] == match), None)
            if game:
                appid = game['appid']
                game_details = await self.get_short_game_info(appid)
                if 'error' not in game_details:
                    found_games.append(game_details)
        
        # Сохраняем результаты в кэше
        self.search_cache[game_name] = found_games
        self.save_cache(self.search_cache_file, self.search_cache)
        
        # Очищаем консоль после завершения
        print("\r", end="")  # Очищаем строку прогресс-бара
        
        return found_games

    async def get_short_game_info(self, appid):
        """Асинхронное получение короткой информации о игре."""
        url = f"http://store.steampowered.com/api/appdetails/"
        params = {'appids': appid}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {"error": "Не удалось получить информацию о игре."}
                
                data = await response.json()
                
                if str(appid) in data and data[str(appid)]['success']:
                    game_data = data[str(appid)]['data']
                    return {
                        "appid": appid,
                        "name": game_data.get('name', 'Название не доступно'),
                        "developers": game_data.get('developers', ['Разработчики не указаны']),
                    }
                else:
                    return {"error": "Информация о игре не доступна."}

    async def get_full_game_info(self, appid):
        """Асинхронное получение подробной информации о игре."""
        url = f"http://store.steampowered.com/api/appdetails/"
        params = {'appids': appid}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {"error": "Не удалось получить информацию о игре."}
                
                data = await response.json()
                
                if str(appid) in data and data[str(appid)]['success']:
                    game_data = data[str(appid)]['data']
                    return {
                        "name": game_data.get('name', 'Название не доступно'),
                        "description": game_data.get('short_description', 'Описание не доступно'),
                        "developers": game_data.get('developers', ['Разработчики не указаны']),
                        "release_date": game_data.get('release_date', {}).get('date', 'Дата выхода не указана'),
                        "steam_url": f"https://store.steampowered.com/app/{appid}"
                    }
                else:
                    return {"error": "Информация о игре не доступна."}

    async def resolve_vanity_url(self, vanity_url):
        """
        Преобразует кастомный URL пользователя в SteamID.
        :param vanity_url: Кастомный URL пользователя (например, "username").
        :return: SteamID пользователя или None, если не найдено.
        """
        url = f"{self.base_url}/ISteamUser/ResolveVanityURL/v1/"
        params = {
            "key": self.api_key,
            "vanityurl": vanity_url
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise Exception("Не удалось разрешить кастомный URL.")
                
                data = await response.json()
                if data['response']['success'] == 1:
                    return data['response']['steamid']
                else:
                    return None

    async def get_player_summaries(self, steamids):
        """
        Получает информацию о пользователях по их SteamID.
        :param steamids: Список SteamID пользователей.
        :return: Список словарей с информацией о пользователях.
        """
        url = f"{self.base_url}/ISteamUser/GetPlayerSummaries/v2/"
        params = {
            "key": self.api_key,
            "steamids": ",".join(steamids)
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise Exception("Не удалось получить информацию о пользователях.")
                
                data = await response.json()
                return data['response']['players']
            
    async def get_account_creation_date(self, steamid):
        """
        Получает дату создания аккаунта через ISteamUser/GetPlayerSummaries.
        :param steamid: SteamID пользователя.
        :return: Дата создания аккаунта (в формате Unix timestamp) или None, если не удалось получить.
        """
        url = f"{self.base_url}/ISteamUser/GetPlayerSummaries/v2/"
        params = {
            "key": self.api_key,
            "steamids": steamid
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise Exception("Не удалось получить информацию о пользователе.")
                
                data = await response.json()
                players = data['response']['players']
                if players:
                    player = players[0]
                    return player.get('timecreated')  # Время создания аккаунта в Unix timestamp
        return None

    async def search_user_by_name(self, username):
        """
        Поиск пользователя по имени (кастомному URL).
        :param username: Имя пользователя (кастомный URL).
        :return: Информация о пользователе или сообщение об ошибке.
        """
        steamid = await self.resolve_vanity_url(username)
        if not steamid:
            return {"error": "Пользователь не найден."}
        
        users = await self.get_player_summaries([steamid])
        if users:
            user = users[0]
            
            # Получаем дату создания аккаунта
            time_created = await self.get_account_creation_date(steamid)
            creation_date = datetime.fromtimestamp(time_created).strftime('%Y-%m-%d %H:%M:%S') if time_created else "Неизвестно"
            
            return {
                "steamid": user.get("steamid"),
                "personaname": user.get("personaname"),
                "profileurl": user.get("profileurl"),
                "avatar": user.get("avatarfull"),
                "lastlogoff": user.get("lastlogoff"),
                "personastate": user.get("personastate"),
                "description": user.get("realname", "Не указано"),  # Описание профиля
                "account_creation_date": creation_date  # Дата регистрации
            }
        else:
            return {"error": "Информация о пользователе не доступна."}