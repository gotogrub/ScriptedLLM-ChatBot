REQUEST_SPECS = {
    "stationery_order": {
        "title": "Заказ канцтоваров и продуктов",
        "service": "procurement",
        "required_fields": ["employee", "items", "item_quantities", "office", "delivery_priority"],
        "allowed_categories": ["procurement", "offices"],
        "questions": {
            "employee": "Уточните ФИО сотрудника, для которого оформить заказ.",
            "items": "Напишите, что нужно заказать. Можно перечислить товары или прислать ссылку.",
            "item_quantities": "Уточните количество по каждой позиции.",
            "office": "Укажите офис или точный адрес доставки.",
            "delivery_priority": "Уточните срочность: срочно, сегодня или планово.",
        },
        "quick_replies": {
            "delivery_priority": ["Срочно", "Сегодня", "Планово"],
            "office": ["Центральный офис", "Склад", "Сервис-центр"],
        },
    },
    "sim_card": {
        "title": "Корпоративная SIM-карта",
        "service": "telecom",
        "required_fields": ["employee", "department", "manager", "sim_type", "roaming"],
        "allowed_categories": ["sim", "employees"],
        "questions": {
            "employee": "Уточните ФИО сотрудника, на которого нужна SIM-карта.",
            "department": "Укажите подразделение сотрудника.",
            "manager": "Укажите руководителя для согласования.",
            "sim_type": "Какой тип SIM нужен: физическая SIM или eSIM?",
            "roaming": "Нужен международный роуминг?",
        },
        "quick_replies": {
            "sim_type": ["eSIM", "Физическая SIM"],
            "roaming": ["Роуминг нужен", "Роуминг не нужен"],
        },
    },
    "business_trip": {
        "title": "Командировка: трансфер и проживание",
        "service": "travel",
        "required_fields": ["employee", "city", "start_date", "nights", "hotel_preferences", "transfer_needed"],
        "allowed_categories": ["travel", "employees"],
        "questions": {
            "employee": "Уточните ФИО командируемого сотрудника.",
            "city": "Укажите город командировки.",
            "start_date": "Укажите дату начала поездки.",
            "nights": "Укажите количество ночей.",
            "hotel_preferences": "Укажите пожелания к проживанию.",
            "transfer_needed": "Нужен трансфер?",
        },
        "quick_replies": {
            "hotel_preferences": ["Без предпочтений", "Рядом с офисом", "Тихий номер"],
            "transfer_needed": ["Трансфер нужен", "Трансфер не нужен"],
        },
    },
    "parking_pass": {
        "title": "Пропуск на парковку БЦ",
        "service": "facility",
        "required_fields": ["employee", "car_number", "car_brand", "valid_until"],
        "allowed_categories": ["parking", "employees", "offices"],
        "questions": {
            "employee": "Уточните ФИО сотрудника.",
            "car_number": "Укажите номер автомобиля.",
            "car_brand": "Укажите марку автомобиля.",
            "valid_until": "Укажите срок действия пропуска.",
        },
        "quick_replies": {
            "valid_until": ["На день", "На неделю", "На месяц"],
        },
    },
    "taxi_order": {
        "title": "Заказ такси",
        "service": "transport",
        "required_fields": ["employee", "pickup", "destination", "time", "passengers"],
        "allowed_categories": ["taxi", "employees", "offices"],
        "questions": {
            "employee": "Уточните ФИО пассажира.",
            "pickup": "Укажите точку подачи.",
            "destination": "Укажите точку назначения.",
            "time": "Укажите время подачи.",
            "passengers": "Сколько пассажиров поедет?",
        },
        "quick_replies": {
            "pickup": ["Центральный офис", "Склад", "Сервис-центр"],
            "passengers": ["1 пассажир", "2 пассажира", "3 пассажира"],
        },
    },
    "disorder_report": {
        "title": "Обратная связь Непорядок",
        "service": "incident",
        "required_fields": ["employee", "problem_category", "location", "criticality"],
        "allowed_categories": ["incidents", "offices", "employees"],
        "questions": {
            "employee": "Уточните ФИО заявителя.",
            "problem_category": "Опишите проблему.",
            "location": "Укажите локацию: центральный офис, склад или сервис-центр.",
            "criticality": "Оцените критичность: низкая, средняя или высокая.",
        },
        "quick_replies": {
            "location": ["Центральный офис", "Склад", "Сервис-центр"],
            "criticality": ["Высокая", "Средняя", "Низкая"],
        },
    },
}


FIELD_LABELS = {
    "employee": "Сотрудник",
    "items": "Позиции",
    "item_quantities": "Количество",
    "office": "Офис",
    "delivery_priority": "Срочность",
    "department": "Подразделение",
    "manager": "Руководитель",
    "sim_type": "Тип SIM",
    "roaming": "Международный роуминг",
    "city": "Город",
    "start_date": "Дата начала",
    "nights": "Ночей",
    "hotel_preferences": "Пожелания к отелю",
    "transfer_needed": "Трансфер",
    "car_number": "Номер автомобиля",
    "car_brand": "Марка автомобиля",
    "valid_until": "Срок действия",
    "pickup": "Точка подачи",
    "destination": "Точка назначения",
    "time": "Время",
    "passengers": "Пассажиры",
    "problem_category": "Категория проблемы",
    "location": "Локация",
    "criticality": "Критичность",
}


SCENARIO_CHOICES = [
    ("stationery_order", "Заказ канцтоваров"),
    ("sim_card", "SIM-карта"),
    ("business_trip", "Командировка"),
    ("parking_pass", "Парковка"),
    ("taxi_order", "Такси"),
    ("disorder_report", "Непорядок"),
]
