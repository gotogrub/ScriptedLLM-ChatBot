from datetime import date, datetime, time, timedelta
import re


NUMBER_WORDS = {
    "один": 1,
    "одна": 1,
    "одно": 1,
    "одну": 1,
    "одного": 1,
    "одной": 1,
    "пара": 2,
    "пару": 2,
    "две": 2,
    "два": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
}


ITEM_KEYWORDS = {
    "ручк": {
        "name": "Ручки",
        "category": "Канцтовары",
        "supplier": "Комус",
        "url": "https://komus.example/catalog/pens",
    },
    "карандаш": {
        "name": "Карандаши",
        "category": "Канцтовары",
        "supplier": "Комус",
        "url": "https://komus.example/catalog/pencils",
    },
    "блокнот": {
        "name": "Блокнот",
        "category": "Канцтовары",
        "supplier": "Комус",
        "url": "https://komus.example/catalog/notebooks",
    },
    "бумаг": {
        "name": "Бумага А4",
        "category": "Канцтовары",
        "supplier": "Комус",
        "url": "https://komus.example/catalog/a4-paper",
    },
    "а4": {
        "name": "Бумага А4",
        "category": "Канцтовары",
        "supplier": "Комус",
        "url": "https://komus.example/catalog/a4-paper",
    },
    "маркер": {
        "name": "Маркеры",
        "category": "Канцтовары",
        "supplier": "Комус",
        "url": "https://komus.example/catalog/markers",
    },
    "стикер": {
        "name": "Стикеры",
        "category": "Канцтовары",
        "supplier": "Комус",
        "url": "https://komus.example/catalog/sticky-notes",
    },
    "коф": {
        "name": "Кофе",
        "category": "Продукты",
        "supplier": "ВкусВилл",
        "url": "https://vkusvill.example/catalog/coffee",
    },
    "молок": {
        "name": "Молоко",
        "category": "Продукты",
        "supplier": "ВкусВилл",
        "url": "https://vkusvill.example/catalog/milk",
    },
    "чай": {
        "name": "Чай",
        "category": "Продукты",
        "supplier": "ВкусВилл",
        "url": "https://vkusvill.example/catalog/tea",
    },
    "сахар": {
        "name": "Сахар",
        "category": "Продукты",
        "supplier": "ВкусВилл",
        "url": "https://vkusvill.example/catalog/sugar",
    },
    "печень": {
        "name": "Печенье",
        "category": "Продукты",
        "supplier": "ВкусВилл",
        "url": "https://vkusvill.example/catalog/cookies",
    },
    "вод": {
        "name": "Вода",
        "category": "Продукты",
        "supplier": "ВкусВилл",
        "url": "https://vkusvill.example/catalog/water",
    },
    "стаканчик": {
        "name": "Стаканчики",
        "category": "Кухня",
        "supplier": "Комус",
        "url": "https://komus.example/catalog/cups",
    },
    "салфет": {
        "name": "Салфетки",
        "category": "Кухня",
        "supplier": "Комус",
        "url": "https://komus.example/catalog/napkins",
    },
}


CITIES = {
    "питер": "Санкт-Петербург",
    "санкт-петербург": "Санкт-Петербург",
    "спб": "Санкт-Петербург",
    "ереван": "Ереван",
    "казань": "Казань",
    "алматы": "Алматы",
    "новосибирск": "Новосибирск",
    "москва": "Москва",
}


CAR_BRANDS = [
    "Toyota",
    "Hyundai",
    "Kia",
    "Volkswagen",
    "Skoda",
    "Lada",
    "BMW",
    "Mercedes",
    "Audi",
    "Nissan",
]


def lower_text(text):
    return text.lower().replace("ё", "е")


def first_number(text):
    match = re.search(r"\b\d+\b", text)
    if match:
        return int(match.group(0))
    value = lower_text(text)
    for word, number in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", value):
            return number
    return None


def numbers(text):
    found = [int(item) for item in re.findall(r"\b\d+\b", text)]
    value = lower_text(text)
    for word, number in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", value):
            found.append(number)
    return found


def quantity_mentions(text):
    value = lower_text(text)
    found = []
    for match in re.finditer(r"\b\d+\b", value):
        found.append({"quantity": int(match.group(0)), "pos": match.start()})
    for word, number in NUMBER_WORDS.items():
        for match in re.finditer(rf"\b{word}\b", value):
            found.append({"quantity": number, "pos": match.start()})
    found.sort(key=lambda item: item["pos"])
    return found


def extract_employee(text, repository, user_id, request_type):
    employee = repository.find_employee(text)
    if employee:
        return employee["name"]
    value = lower_text(text)
    if request_type == "sim_card" and ("нового" in value or "новый" in value):
        return None
    if any(word in value for word in ["мне", "меня", "мой", "мою", "я ", "закажи"]):
        current = repository.get_employee_by_user_id(user_id)
        if current:
            return current["name"]
    if request_type in ["stationery_order", "taxi_order", "business_trip", "parking_pass", "disorder_report"]:
        current = repository.get_employee_by_user_id(user_id)
        if current:
            return current["name"]
    return None


def extract_office(text):
    value = lower_text(text)
    if "централь" in value or "москва-сити" in value or "офис" in value:
        return "Центральный офис"
    if "склад" in value:
        return "Склад"
    if "сервис" in value:
        return "Сервис-центр"
    return None


def extract_items(text, current_draft):
    value = lower_text(text)
    found = []
    url_match = re.search(r"https?://\S+", text)
    if url_match:
        found.append({"name": "Товар по ссылке", "quantity": first_number(text), "url": url_match.group(0)})
    for key, item in ITEM_KEYWORDS.items():
        if key in value:
            found.append({**item, "quantity": None, "_pos": value.find(key)})
    found.sort(key=lambda item: item.get("_pos", 0))
    found = unique_items(found)
    if not found and current_draft.get("items"):
        found = [dict(item) for item in current_draft.get("items", [])]
    quantities = quantity_mentions(text)
    if found and any("_pos" in item for item in found):
        assign_quantities_to_items(found, quantities)
    if current_draft.get("items") and quantities:
        existing = [dict(item) for item in current_draft.get("items", [])]
        missing = [item for item in existing if not item.get("quantity")]
        if len(missing) == 1:
            missing[0]["quantity"] = quantities[0]["quantity"]
            return existing
        if len(quantities) == len(existing):
            for index, quantity in enumerate(quantities):
                existing[index]["quantity"] = quantity["quantity"]
            return existing
    for item in found:
        item.pop("_pos", None)
    return unique_items(found)


def assign_quantities_to_items(items, mentions):
    used = set()
    for item in items:
        item_pos = item.get("_pos")
        if item_pos is None:
            continue
        before = [
            (index, mention)
            for index, mention in enumerate(mentions)
            if index not in used and mention["pos"] <= item_pos and item_pos - mention["pos"] <= 48
        ]
        after = [
            (index, mention)
            for index, mention in enumerate(mentions)
            if index not in used and mention["pos"] > item_pos and mention["pos"] - item_pos <= 18
        ]
        candidates = before or after
        if candidates:
            index, mention = min(candidates, key=lambda pair: abs(item_pos - pair[1]["pos"]))
            item["quantity"] = mention["quantity"]
            used.add(index)
    unfilled = [item for item in items if not item.get("quantity")]
    unused = [mention for index, mention in enumerate(mentions) if index not in used]
    if len(unfilled) == len(unused):
        for item, mention in zip(unfilled, unused):
            item["quantity"] = mention["quantity"]


def unique_items(items):
    unique = []
    seen = set()
    for item in items:
        marker = item.get("url") or item["name"]
        if marker not in seen:
            unique.append(item)
            seen.add(marker)
    return unique


def extract_delivery_priority(text):
    value = lower_text(text)
    if "срочно" in value or "как можно скорее" in value:
        return "Срочно"
    if "сегодня" in value:
        return "Сегодня"
    if "план" in value:
        return "Планово"
    return None


def parse_date_value(text):
    value = lower_text(text)
    today = date.today()
    if "послезавтра" in value:
        return today + timedelta(days=2)
    if "завтра" in value:
        return today + timedelta(days=1)
    if "сегодня" in value:
        return today
    if "следующ" in value and "недел" in value:
        days_until_monday = 7 - today.weekday()
        return today + timedelta(days=days_until_monday)
    match = re.search(r"\b(\d{1,2})[.\/-](\d{1,2})(?:[.\/-](\d{2,4}))?\b", text)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def parse_time_value(text):
    value = lower_text(text)
    if "утром" in value:
        return time(9, 0)
    if "днем" in value:
        return time(13, 0)
    if "вечером" in value:
        return time(18, 0)
    match = re.search(r"\b(\d{1,2})[:.](\d{2})\b", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)
    match = re.search(r"\bв\s+(\d{1,2})\b", value)
    if match:
        hour = int(match.group(1))
        if 0 <= hour <= 23:
            return time(hour, 0)
    return None


def parse_datetime_value(text):
    value = lower_text(text)
    now = datetime.now().replace(second=0, microsecond=0)
    match = re.search(r"через\s+(\d+)\s+мин", value)
    if match:
        return (now + timedelta(minutes=int(match.group(1)))).isoformat(timespec="minutes")
    day_value = parse_date_value(text) or now.date()
    time_value = parse_time_value(text) or time(9, 0)
    return datetime.combine(day_value, time_value).isoformat(timespec="minutes")


def extract_city(text):
    value = lower_text(text)
    for key, city in CITIES.items():
        if key in value:
            return city
    match = re.search(r"\bв\s+([А-Яа-яA-Za-z-]{4,})", text)
    if match:
        raw = match.group(1).strip(" ,.")
        if raw.lower() not in ["офис", "аэропорт", "переговорке", "центре"]:
            return raw[:1].upper() + raw[1:]
    return None


def extract_nights(text):
    value = lower_text(text)
    match = re.search(r"\bна\s+(\d+)\s+ноч", value)
    if match:
        return int(match.group(1))
    if "недел" in value:
        return 5
    number = first_number(text)
    if number and "ноч" in value:
        return number
    return None


def extract_route(text):
    value = lower_text(text)
    result = {}
    match = re.search(r"из\s+(.+?)\s+в\s+(.+?)(?:\s+(?:завтра|сегодня|через|для|на|к|ко|$)|$)", value)
    if match:
        result["pickup"] = clean_place(match.group(1))
        result["destination"] = clean_place(match.group(2))
    match = re.search(r"от\s+(.+?)\s+до\s+(.+?)(?:\s+(?:завтра|сегодня|через|для|на|к|ко|$)|$)", value)
    if match:
        result["pickup"] = clean_place(match.group(1))
        result["destination"] = clean_place(match.group(2))
    if "до аэропорт" in value or "в аэропорт" in value:
        result.setdefault("destination", "Аэропорт")
    for airport in ["шереметьево", "домодедово", "внуково"]:
        if airport in value:
            result["destination"] = airport[:1].upper() + airport[1:]
    office = extract_office(text)
    if office and "pickup" not in result:
        result["pickup"] = office
    return result


def extract_passengers(text):
    value = lower_text(text)
    patterns = [
        r"\b(\d+)\s+пассаж",
        r"\b(\d+)\s+человек",
        r"\b(\d+)\s+чел",
        r"\bдля\s+(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return int(match.group(1))
    for word, number in NUMBER_WORDS.items():
        if f"{word} пассаж" in value or f"{word} человек" in value:
            return number
    return None


def clean_place(value):
    cleaned = value.strip(" ,.")
    if "офис" in cleaned:
        return "Центральный офис"
    return cleaned[:1].upper() + cleaned[1:]


def extract_car_number(text):
    match = re.search(r"\b[АВЕКМНОРСТУХABEKMHOPCTYX]\s?\d{3}\s?[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\s?\d{2,3}\b", text, re.IGNORECASE)
    if match:
        return re.sub(r"\s+", "", match.group(0)).upper()
    return None


def extract_car_brand(text):
    value = lower_text(text)
    for brand in CAR_BRANDS:
        if brand.lower() in value:
            return brand
    return None


def extract_valid_until(text):
    value = lower_text(text)
    today = date.today()
    if "день" in value:
        return today.isoformat()
    if "недел" in value:
        return (today + timedelta(days=7)).isoformat()
    if "месяц" in value:
        return (today + timedelta(days=30)).isoformat()
    day_value = parse_date_value(text)
    if day_value:
        return day_value.isoformat()
    return None


def extract_problem_category(text):
    value = lower_text(text)
    if "туалет" in value or "бумаг" in value or "стаканчик" in value:
        return "Расходники"
    if "кондиционер" in value or "температур" in value:
        return "Климат"
    if "кофемашин" in value or "принтер" in value:
        return "Оборудование"
    if "гряз" in value or "уборк" in value:
        return "Чистота"
    if len(value) > 8:
        return text.strip()
    return None


def extract_location(text):
    value = lower_text(text)
    if "переговор" in value:
        return "Переговорная"
    return extract_office(text)


def extract_criticality(text):
    value = lower_text(text)
    if any(word in value for word in ["срочно", "критично", "не работает", "сломал", "авар"]):
        return "Высокая"
    if any(word in value for word in ["законч", "нет", "мало"]):
        return "Средняя"
    if any(word in value for word in ["низкая", "потом", "не срочно"]):
        return "Низкая"
    return None


def extract_entities(request_type, text, repository, user_id, current_draft):
    result = {}
    employee = extract_employee(text, repository, user_id, request_type)
    if employee:
        result["employee"] = employee
    if request_type == "stationery_order":
        items = extract_items(text, current_draft)
        if items:
            result["items"] = items
        office = extract_office(text)
        if office:
            result["office"] = office
        priority = extract_delivery_priority(text)
        if priority:
            result["delivery_priority"] = priority
    if request_type == "sim_card":
        value = lower_text(text)
        employee_record = repository.find_employee(text)
        if employee_record:
            result["department"] = employee_record["department"]
            result["manager"] = employee_record["manager"]
        if "esim" in value or "e-sim" in value:
            result["sim_type"] = "eSIM"
        elif "физ" in value or "обыч" in value:
            result["sim_type"] = "Физическая SIM"
        if "роуминг" in value:
            result["roaming"] = "не нужен" not in value and "без" not in value
        if "подраздел" in value:
            result["department"] = text.strip()
    if request_type == "business_trip":
        city = extract_city(text)
        if city:
            result["city"] = city
        day_value = parse_date_value(text)
        if day_value:
            result["start_date"] = day_value.isoformat()
        nights = extract_nights(text)
        if nights:
            result["nights"] = nights
        value = lower_text(text)
        if "без предпочт" in value:
            result["hotel_preferences"] = "Без предпочтений"
        elif "рядом" in value:
            result["hotel_preferences"] = "Рядом с офисом"
        elif "тих" in value:
            result["hotel_preferences"] = "Тихий номер"
        if "трансфер" in value:
            result["transfer_needed"] = "не нужен" not in value and "без" not in value
    if request_type == "parking_pass":
        car_number = extract_car_number(text)
        if car_number:
            result["car_number"] = car_number
        brand = extract_car_brand(text)
        if brand:
            result["car_brand"] = brand
        valid_until = extract_valid_until(text)
        if valid_until:
            result["valid_until"] = valid_until
    if request_type == "taxi_order":
        result.update(extract_route(text))
        value = lower_text(text)
        if "через" in value or "завтра" in value or "сегодня" in value or re.search(r"\bв\s+\d{1,2}", value):
            result["time"] = parse_datetime_value(text)
        passenger_count = extract_passengers(text)
        if passenger_count:
            result["passengers"] = passenger_count
    if request_type == "disorder_report":
        category = extract_problem_category(text)
        if category:
            result["problem_category"] = category
        location = extract_location(text)
        if location:
            result["location"] = location
        criticality = extract_criticality(text)
        if criticality:
            result["criticality"] = criticality
    return result
