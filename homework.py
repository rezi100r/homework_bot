import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv
from http import HTTPStatus
from typing import Union

from exceptions import HTTPRequestError, CheckResponseError, ParseStatusError
from exceptions import LenResponseError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

MESSAGES = {
    'error': '',
    'message': '',
}


def send_message(bot: telegram.Bot, message: str) -> None:
    """отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Бот отправил сообщение {message}')
    except Exception as error:
        logging.error(error)


def get_api_answer(current_timestamp: int) -> Union[dict, str]:
    """создает и отправляет запрос к эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    logging.info(f'Отправка запроса на {ENDPOINT} с параметрами {params}')
    if response.status_code != HTTPStatus.OK:
        raise HTTPRequestError(response)
    return response.json()


def check_response(response: dict) -> list:
    """Проверка полученного ответа от эндпоинта."""
    if not isinstance(response, dict):
        message = 'имеет некорректный тип.'
        logging.error(message)
        raise TypeError(message)

    if not isinstance(response.get('homeworks'), list):
        message = 'формат ответа не соответствует.'
        logging.error(message)
        raise CheckResponseError(message)

    if not response:
        message = 'содержит пустой словарь.'
        logging.error(message)
        raise KeyError(message)

    if 'homeworks' not in response:
        message = 'отсутствие ожидаемых ключей в ответе.'
        logging.error(message)
        raise KeyError(message)

    return response.get('homeworks')


def parse_status(homework: dict) -> str:
    """Извлекает из информации о домашней работе статус этой работы."""
    if not homework.get('homework_name'):
        homework_name = 'NoNaMe'
        logging.warning('Отсутствует имя домашней работы.')
    else:
        homework_name = homework.get('homework_name')

    homework_status = homework.get('status')
    if 'status' not in homework:
        message = 'Отсутстует ключ homework_status.'
        logging.error(message)
        raise ParseStatusError(message)

    verdict = HOMEWORK_STATUSES.get(homework_status)
    if homework_status not in HOMEWORK_STATUSES:
        message = 'Недокументированный статус домашней работы'
        logging.error(message)
        raise KeyError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """проверяет доступность переменных окружения необходимых для работы."""
    list_env = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    if not all(list_env):
        logging.critical(
            'Отсутствует обязательная переменная окружения.\n'
            'Программа принудительно остановлена.'
        )
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                raise LenResponseError
            for homework in homeworks:
                message = parse_status(homework)
                if MESSAGES.get('message') != message:
                    send_message(bot, message)
                    MESSAGES['message'] = message
            current_timestamp = response.get('current_date')
        except LenResponseError as error:
            logging.debug(error)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if MESSAGES['error'] != message:
                send_message(bot, message)
            MESSAGES['error'] = message
        else:
            MESSAGES['error'] = ''
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        stream=sys.stdout

    )
    main()
