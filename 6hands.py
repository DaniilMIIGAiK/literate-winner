import requests

from bs4 import BeautifulSoup
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, unquote


# Функция для получения ссылок из статьи Википедии
def get_links(base_url, page_title):
    url = f"{base_url}/wiki/{page_title}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Ищем все ссылки внутри основного контента статьи
    content_div = soup.find('div', {'id': 'bodyContent'})
    links = set()
    for a_tag in content_div.find_all('a', href=True):
        href = a_tag['href']
        if href.startswith('/wiki/') and ':' not in href:  # Исключаем специальные страницы
            links.add(href[6:])  # Убираем '/wiki/' из URL

    return page_title, links  # Возвращаем название статьи и найденные ссылки


def extract_article_and_base_url(full_url):
    parsed_url = urlparse(full_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    path = parsed_url.path
    if path.startswith('/wiki/'):
        article_name = path[6:]  # Убираем '/wiki/' из пути
        return base_url, unquote(article_name)  # Декодируем URL-кодировку
    
    raise ValueError("Неверный формат URL. Ожидался URL вида https://<language>.wikipedia.org/wiki/<article>")

# Функция для поиска кратчайшей цепочки переходов с ограничением на количество потоков
def find_shortest_path(start_url, target_url, max_connections):
    # Извлекаем базовый URL и названия статей
    start_base_url, start_article = extract_article_and_base_url(start_url)
    target_base_url, target_article = extract_article_and_base_url(target_url)

    # Проверяем, что обе статьи находятся на одном языке
    if start_base_url != target_base_url:
        raise ValueError("Статьи находятся в разных языковых разделах Википедии. Поиск невозможен.")

    visited = set()  # Множество для отслеживания посещенных статей
    queue = deque([(start_article, [start_article])])  # Очередь для BFS: (текущая статья, путь до нее)

    while queue:
        # Собираем задачи для обработки в пуле потоков
        tasks = []
        while queue:
            current_page, path = queue.popleft()
            if current_page not in visited:
                visited.add(current_page)
                tasks.append((current_page, path))  # Добавляем задачу в список

        if not tasks:
            break

        # Используем пул потоков для параллельной обработки задач
        with ThreadPoolExecutor(max_workers=max_connections) as executor:
            futures = {executor.submit(get_links, start_base_url, task[0]): task for task in tasks}

            for future in as_completed(futures):
                try:
                    current_page, links = future.result()
                    original_task = futures[future]  # Получаем оригинальную задачу
                    original_path = original_task[1]

                    # Если достигли целевой статьи, возвращаем путь
                    if current_page == target_article:
                        return original_path

                    # Добавляем новые статьи в очередь
                    for link in links:
                        if link not in visited:
                            queue.append((link, original_path + [link]))

                except Exception as e:
                    print(f"Ошибка при обработке статьи: {e}")

    # Если цель не достигнута за 6 шагов
    return None

# Основная функция
if __name__ == "__main__":
    start_url = input("Введите начальную ссылку (например, https://en.wikipedia.org/wiki/Six_degrees_of_separation): ").strip()
    target_url = input("Введите целевую ссылку (например, https://en.wikipedia.org/wiki/American_Broadcasting_Company): ").strip()
    max_connections = int(input("Введите rate-limit: "))

    result = find_shortest_path(start_url, target_url, 10)

    if result:
        # Формируем полную цепочку URL-адресов
        base_url, _ = extract_article_and_base_url(start_url)
        urls = [f"{base_url}/wiki/{article}" for article in result]
        print(" => ".join(urls))
    else:
        print("Цепочка не найдена за 5 переходов")