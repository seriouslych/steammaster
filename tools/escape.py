import re

def escape_markdown_v2(text):
    """
    Экранирует специальные символы для MarkdownV2.
    """
    if not isinstance(text, str):  # Проверяем, что входные данные — строка
        return str(text)
    # Список символов, которые нужно экранировать: _ * [ ] ( ) ~ ` > # + - = | { } . !
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    # Двойное экранирование обратного слэша
    text = text.replace("\\", "\\\\")
    # Экранирование остальных символов
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)