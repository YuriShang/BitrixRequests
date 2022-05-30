from fast_bitrix24 import Bitrix
from flask import Flask, request


app = Flask(__name__)

# Инициализируем экземпляр класса Bitrix для дальнейшей работы
WEBHOOK = "Ваш вебхук"
my_bitrix = Bitrix(WEBHOOK)

# Список пользовательских полей, которые необходимо добавить в систему b24
user_fields_to_add = [{
        "FIELD_NAME": "PRODUCTS",
        "EDIT_FORM_LABEL": "Предметы",
        "LIST_COLUMN_LABEL": "Предметы",
        "USER_TYPE_ID": "enumeration",
    },
    {
        "FIELD_NAME": "ADDRESS",
        "EDIT_FORM_LABEL": "Адрес доставки",
        "LIST_COLUMN_LABEL": "Адрес доставки",
        "USER_TYPE_ID": "string",
    },
    {
        "FIELD_NAME": "DATE",
        "EDIT_FORM_LABEL": "Дата доставки",
        "LIST_COLUMN_LABEL": "Дата доставки",
        "USER_TYPE_ID": "string",
    },
    {
        "FIELD_NAME": "CODE",
        "EDIT_FORM_LABEL": "Код доставки",
        "LIST_COLUMN_LABEL": "Код доставки",
        "USER_TYPE_ID": "string",
    }]

# Проверяем имеются ли в системе b24 пользовательские поля, если нет, добавляем
user_fields = [field["FIELD_NAME"] for field in my_bitrix.get_all("crm.deal.userfield.list")]
for field_to_add in user_fields_to_add:
    if f'UF_CRM_{field_to_add["FIELD_NAME"]}' not in user_fields:
        my_bitrix.call("crm.deal.userfield.add", field_to_add)


@app.route('/get_data', methods=['POST'])
def get_json():

    request_data = request.get_json()

    if request_data:
        name = request_data["client"]["name"]
        surname = request_data["client"]["surname"]
        address = request_data["client"]["address"]
        phone = ""
        title = request_data["title"]
        description = request_data["description"]
        products = request_data["products"]
        delivery_address = request_data["delivery_address"]
        delivery_date = request_data["delivery_date"]
        delivery_code = request_data["delivery_code"]

        contact_fields = {"NAME": name,
                          "LAST_NAME": surname,
                          "PHONE": phone,
                          "ADDRESS": address}

        deal_fields = {"UF_CRM_PRODUCTS": products,
                       "UF_CRM_ADDRESS": delivery_address,
                       "UF_CRM_DATE": delivery_date,
                       "UF_CRM_CODE": delivery_code,
                       "CONTACT_ID": get_contact_id(phone),
                       "TITLE": title,
                       "COMMENTS": description,
                       }

        # удаляем все лишнее из номера телефона
        for elem in request_data["client"]["phone"]:
            if elem.isdigit():
                phone += elem

        # Запрашиваем все контакты с битрикса
        contacts = my_bitrix.get_all("crm.contact.list", {"select": ["PHONE"]})

        # Отделяем номер
        phones = [contact["PHONE"][0]["VALUE"] for contact in contacts if "PHONE" in contact]

        # Если контакта нет в базе, добавляем контакт, сделку и связываем их
        if phone not in phones:
            my_bitrix.call("crm.contact.add", contact_fields)
            deal_fields["CONTACT_ID"] = get_contact_id(phone)
            my_bitrix.call("crm.deal.add", deal_fields)
            print(f'New contact with phone number {phone} created!')
            print(f'New deal {delivery_code} for this contact created!')

            return f'Deal {delivery_code} and contact with Ph: {phone} created!'

        # В противном случае проверяем есть ли сделка, связанная с контактом
        else:
            # Запрашиваем все сделки
            deals = my_bitrix.get_all("crm.deal.list", {"select": user_fields})

            # Находим заявку контакта
            deal = [field for field in deals if field.get("UF_CRM_CODE") == delivery_code]

            # Создаем поля для обновления сделки
            update_fields = {"UF_CRM_PRODUCTS": None,
                             "UF_CRM_ADDRESS": None,
                             "UF_CRM_DATE": None,
                             }

            # Если сделки нет, создаем новую
            if not deal:
                my_bitrix.call("crm.deal.add", deal_fields)
                print(f"New deal for contact {phone} created!")

                return f"New deal for contact with Ph: {phone} created!"

            # Если есть, проверяем поля на соответствие новым данным
            else:
                deal = deal[0]
                for uf, df in zip(update_fields, deal):
                    if deal[uf] != deal_fields[uf]:
                        update_fields[uf] = deal_fields[uf]

                # Если поля отличаются, обновляем их
                for k, v in update_fields.items():
                    if v:
                        my_bitrix.call("crm.deal.update", {"ID": deal["ID"], k: v})
                        print(f'Deal with code {delivery_code} updated')

                return f"Fields {[f'{k} = {v}' for k, v in update_fields.items() if v]} " \
                       f"for contact with Ph: {phone} updated!"

    return "No changes!"


def get_contact_id(phone):
    # Получаем ID контакта
    contact = my_bitrix.get_all("crm.contact.list", {"select": ["ID", "PHONE"]})
    contact_id = ''.join([c["ID"] for c in contact if c.get("PHONE") and c["PHONE"][0]["VALUE"] == phone])

    return contact_id


if __name__ == '__main__':
    app.run(debug=True, port=5000)
