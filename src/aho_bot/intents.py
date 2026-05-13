from aho_bot.domain import SCENARIO_CHOICES


REQUEST_KEYWORDS = {
    "stationery_order": [
        "канц",
        "ручк",
        "блокнот",
        "бумаг",
        "маркер",
        "комус",
        "вкусвилл",
        "кофе",
        "молок",
        "чай",
        "стаканчик",
        "товар",
        "закажи",
        "купить",
    ],
    "sim_card": [
        "sim",
        "сим",
        "симк",
        "esim",
        "номер",
        "роуминг",
    ],
    "business_trip": [
        "командиров",
        "отель",
        "гостиниц",
        "проживан",
        "трансфер",
        "питер",
        "санкт",
        "ереван",
        "поездк",
    ],
    "parking_pass": [
        "парков",
        "стоянк",
        "пропуск",
        "машин",
        "автомоб",
    ],
    "taxi_order": [
        "такси",
        "аэропорт",
        "шереметьево",
        "домодедово",
        "внуково",
        "поехать",
    ],
    "disorder_report": [
        "непорядок",
        "сломал",
        "не работает",
        "законч",
        "нет",
        "гряз",
        "кондиционер",
        "кофемашин",
        "туалет",
    ],
}


CONTROL_KEYWORDS = {
    "confirm": ["да", "подтверждаю", "подтвердить", "создать", "создавай", "оформить", "оформи"],
    "cancel": ["отмена", "отменить", "сброс", "сбросить", "не надо"],
    "edit": ["изменить", "поменять", "редактировать", "исправить"],
    "status": ["статус", "мои заявки", "что с заявкой", "решении заявки", "решение заявки"],
}


def normalize(text):
    return " ".join(text.lower().replace("ё", "е").split())


def classify_request_type(text):
    value = normalize(text)
    scores = {}
    for request_type, words in REQUEST_KEYWORDS.items():
        score = sum(1 for word in words if word in value)
        if score:
            scores[request_type] = score
    if not scores:
        for request_type, label in SCENARIO_CHOICES:
            if normalize(label) in value:
                return request_type
        return None
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)[0][0]


def classify_control(text):
    value = normalize(text)
    for intent, words in CONTROL_KEYWORDS.items():
        if any(word in value for word in words):
            return intent
    return None


def is_capability_question(text):
    value = normalize(text)
    question_markers = ["что", "какие", "чем", "умеешь", "можешь", "можно"]
    scope_markers = ["заказать", "оформить", "заявк", "помочь", "доступно", "услуг"]
    if any(marker in value for marker in question_markers) and any(marker in value for marker in scope_markers):
        return True
    return False


def is_procurement_capability_question(text):
    value = normalize(text)
    return is_capability_question(text) and any(word in value for word in ["заказать", "товар", "купить"])
