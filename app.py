import re
import asyncio
import json
import os
import calendar
import keyboards as kb 
from datetime import datetime
from num2words import num2words
from config import BOT_TOKEN, ALLOWED_USERS, ADMIN_ID
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, ReplyKeyboardRemove, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from docling_qa import ask_ai_from_pdf
from docling_qa2 import ask_ai_from_pdf2
from docx_replacer import fill_doc
from parse_pko_new_version import parse_contract_data_from_pdf, parse_active_total
from parse_pko_old_ru_version import parse_old_ru_contract_data_from_pdf, parse_old_ru_total_contracts
from parse_pko_old_kz_version import parse_pko_old_kz_version, parse_old_kz_total_contracts
from parse_pro_green_ru_version import parse_old_green_ru_total_contracts, parse_pko_green_ru_version
from datetime import datetime
import unicodedata
from utils import add_user, is_user_allowed, get_user_list, remove_user
from datetime import datetime, timedelta







bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class FileInfo(StatesGroup):
    user_text = State()
    file_path = State()
    reason = State()
    MFO = State()
    mfo = State()
    attached_documents = State()

class BatchProcess(StatesGroup):
    file_path = State()
    user_text = State()
    mfo_list = State()
    reason = State()
    attached_documents = State()
    file_version = State()


def is_authorized(func):
    async def wrapper(message: Message, *args, **kwargs):
        if is_user_allowed(message.from_user.id):
            return await func(message, *args, **kwargs)
        else:
            await message.answer("🚫 У вас нет доступа. Хотите запросить его?",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="📩 Запросить доступ", callback_data="request_access")]
                             ]))
    return wrapper

@dp.message(Command("users"))
async def list_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = get_user_list()
    if not users:
        await message.answer("📭 Список пользователей пуст.")
        return

    text = "📋 <b>Список пользователей:</b>\n\n"
    for uid, info in users.items():
        name = f"{info.get('first_name', '')} {info.get('last_name', '')}".strip()
        username = f"@{info.get('username')}" if info.get('username') else "—"
        text += f"• <b>{name}</b> {username} — <code>{uid}</code>\n/remove_{uid}\n\n"

    await message.answer(text, parse_mode="HTML")


@dp.message(F.text.startswith("/remove_"))
async def remove_user_command(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    user_id = int(message.text.split("_")[1])
    remove_user(user_id)
    await message.answer(f"❌ Пользователь {user_id} удалён.")
    try:
        await bot.send_message(user_id, "⚠️ Ваш доступ к боту был удалён администратором.")
    except:
        pass  # если пользователь заблокировал бота




@dp.callback_query(F.data == "request_access")
async def request_access(callback: CallbackQuery):
    await callback.message.edit_text("✅ Запрос отправлен администратору. Пожалуйста, ожидайте одобрения.")
    user = callback.from_user
    await callback.answer("⏳ Запрос отправлен админу.")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ 7 дней", callback_data=f"grant:{user.id}:7")],
        [InlineKeyboardButton(text="✅ 14 дней", callback_data=f"grant:{user.id}:14")],
        [InlineKeyboardButton(text="✅ 30 дней", callback_data=f"grant:{user.id}:30")],
        [InlineKeyboardButton(text="✅ Навсегда", callback_data=f"grant:{user.id}:0")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"deny:{user.id}")]
    ])

    await bot.send_message(ADMIN_ID,
        f"📥 Запрос от @{user.username or '-'}\nID: {user.id}\nИмя: {user.first_name}",
        reply_markup=keyboard)
    
    
@dp.callback_query(F.data.startswith("grant:"))
async def grant_access(callback: CallbackQuery):
    _, user_id, days = callback.data.split(":")
    user_id = int(user_id)
    days = int(days)

    user = await bot.get_chat(user_id)

    # Вычисляем дату окончания
    if days == 0:
        until = "бессрочно"
    else:
        end_date = datetime.now() + timedelta(days=days)
        until = end_date.strftime("%d.%m.%Y")

    # Добавляем пользователя с датой окончания
    add_user(user_id, user.first_name, user.last_name or "", user.username or "", days)

    await callback.answer("✅ Доступ выдан.")

    # Сообщение для пользователя
    try:
        await bot.send_message(
            user_id,
            f"✅ Вам выдан доступ до {until}." if days else "✅ Вам выдан постоянный доступ."
        )
    except:
        pass

    # Обновляем сообщение админа (удаляем кнопки + пишем кому выдано)
    full_name = f"{user.first_name} {user.last_name}".strip()
    username = f"@{user.username}" if user.username else ""
    await callback.message.edit_text(
        f"✅ Доступ выдан пользователю {full_name} {username} (ID: <code>{user_id}</code>) до <b>{until}</b>.",
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("deny:"))
async def deny_access(callback: CallbackQuery):
    _, user_id = callback.data.split(":")
    await callback.answer("❌ Запрос отклонён.")
    try:
        await bot.send_message(user_id, "🚫 Ваш запрос на доступ был отклонён.")
    except:
        pass





def remove_cents(value: str) -> str:
            # Удаляет копейки после точки или запятой
            return re.sub(r'[.,]\d{1,2}$', '', value)
    

def clean(name: str) -> str:
    # Убираем невидимые символы Unicode (все категории "Cf" — форматирующие)
    name = ''.join(ch for ch in name if unicodedata.category(ch) != 'Cf')
    # Удаляем обычные пробелы, табы, неразрывные пробелы
    return re.sub(r"[ \t\u00A0]+", "", name).strip().lower()


def get_current_date_str():
    return datetime.now().strftime("%d.%m.%Y")


def get_term_by_amount(amount_str):
    # Удаляем все пробелы и валюты, только цифры
    digits_only = ''.join(filter(str.isdigit, amount_str))
    
    if not digits_only:
        return "❌ Некорректная сумма"

    amount = int(digits_only)

    if amount < 100_000:
        return "от 3 до 6 месяцев"
    elif amount < 150_000:
        return "от 6 до 12 месяцев"
    else:
        return "от 12 до 24 месяцев"


# Функция для загрузки данных из файла JSON
def load_companies_db():
    try:
        with open("companies_db.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        print("Файл companies_db.json не найден.")
        return []
    except json.JSONDecodeError:
        print("Ошибка при разборе JSON.")
        return []

def normalize_string(s):
    return re.sub(r'\s+', '', s).lower()  # удаляет ВСЕ пробельные символы и приводит к нижнему регистру

def find_company_by_trade_name(trade_name):
    normalized_trade_name = normalize_string(trade_name)
    companies_data = load_companies_db()
    for company in companies_data:
        if normalize_string(company["trade_name"]) == normalized_trade_name:
            return company
    return None

def pluralize(value, one, few, many):
    # Функция для склонения слова в зависимости от числа
    if 11 <= value % 100 <= 14:
        return many
    elif value % 10 == 1:
        return one
    elif 2 <= value % 10 <= 4:
        return few
    else:
        return many

def calculate_date_diff(start_date_str, end_date_str):
    start_date = datetime.strptime(start_date_str, "%d.%m.%Y")
    end_date = datetime.strptime(end_date_str, "%d.%m.%Y")
    
    if end_date < start_date:
        return "❌ Конечная дата раньше начальной"

    years = end_date.year - start_date.year
    months = end_date.month - start_date.month
    days = end_date.day - start_date.day

    if days < 0:
        months -= 1
        prev_month = end_date.month - 1 if end_date.month > 1 else 12
        prev_year = end_date.year if end_date.month > 1 else end_date.year - 1
        days_in_prev_month = calendar.monthrange(prev_year, prev_month)[1]
        days += days_in_prev_month

    if months < 0:
        years -= 1
        months += 12

    result = []
    if years > 0:
        result.append(f"{years} {pluralize(years, 'год', 'года', 'лет')}")
    if months > 0:
        result.append(f"{months} {pluralize(months, 'месяц', 'месяца', 'месяцев')}")
    if days > 0:
        result.append(f"{days} {pluralize(days, 'день', 'дня', 'дней')}")

    return " и ".join(result) if result else "менее дня"





# @dp.message(F.document)
# async def cmd_batch(message: Message, state: FSMContext):
#     await state.set_state(BatchProcess.file_path)
#     await message.answer("📄 Пожалуйста, сначала отправьте PDF-файл с описанием. (Жирный клиент)")

@dp.message(F.document)
@is_authorized
async def handle_pdf_with_text(message: Message, state: FSMContext, **kwargs):
    document = message.document

    if document.mime_type != "application/pdf":
        await message.answer("❌ Пожалуйста, отправьте PDF-файл.")
        return

    if not message.caption or not message.caption.strip():
        await message.answer("❗ Пожалуйста, добавьте описание к PDF-файлу.")
        return

    file_path = f"temp/{message.from_user.id}_{document.file_name}"
    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=file_path)

    await state.update_data(user_text=message.caption.strip(), file_path=file_path)
    await state.set_state(BatchProcess.file_version)
    await message.answer("📋 Выберите версию файла:", reply_markup=kb.select_file_version)



@dp.message(BatchProcess.file_version)
async def handle_choose_file_version(message: Message, state: FSMContext):
    if message.text not in ["Новая версия(рус)", "Старая версия(рус)", "Зеленая версия(каз)", "Зеленая версия(рус)"]:
        await message.answer("Нет такого варианта", reply_markup=ReplyKeyboardRemove())
        return
    
    await state.update_data(file_version=message.text)

    await state.set_state(BatchProcess.mfo_list)
    await message.answer("📋 Введите список торговых названий, каждое с новой строки:", reply_markup=ReplyKeyboardRemove())

@dp.message(BatchProcess.mfo_list)
async def handle_mfo_list(message: Message, state: FSMContext):
    raw_mfos = message.text.splitlines()
    mfo_names = [clean(name) for name in raw_mfos if clean(name)]

    await state.update_data(mfo_names=mfo_names)
    await state.set_state(BatchProcess.reason)
    data = await state.get_data()

    await message.answer("📄 Пожалуйста, напишите причину. Пример:")
    if data["file_version"] == "Новая версия(рус)":

        await message.answer(f"""В настоящее время финансовое положение очень затруднительное в связи с долговой нагрузкой. Я прилагаю все усилия, чтобы решить свою финансовую ситуацию, однако, в силу ряда объективных причин, в том числе значительных затрат на базовые жизненные нужды, я не в состоянии полностью выплатить всю сумму займов единым платежом. Дополнительно имею {parse_active_total(data["file_path"])} действующих кредитных обязательств.""")

    elif data["file_version"] == "Старая версия(рус)":

        await message.answer(f"""В настоящее время финансовое положение очень затруднительное в связи с долговой нагрузкой. Я прилагаю все усилия, чтобы решить свою финансовую ситуацию, однако, в силу ряда объективных причин, в том числе значительных затрат на базовые жизненные нужды, я не в состоянии полностью выплатить всю сумму займов единым платежом. Дополнительно имею {parse_old_ru_total_contracts(data["file_path"])} действующих кредитных обязательств.""")


    elif data["file_version"] == "Зеленая версия(каз)":

        await message.answer(f"""В настоящее время финансовое положение очень затруднительное в связи с долговой нагрузкой. Я прилагаю все усилия, чтобы решить свою финансовую ситуацию, однако, в силу ряда объективных причин, в том числе значительных затрат на базовые жизненные нужды, я не в состоянии полностью выплатить всю сумму займов единым платежом. Дополнительно имею {parse_old_kz_total_contracts(data["file_path"])} действующих кредитных обязательств.""")


    elif data["file_version"] == "Зеленая версия(рус)":

        await message.answer(f"""В настоящее время финансовое положение очень затруднительное в связи с долговой нагрузкой. Я прилагаю все усилия, чтобы решить свою финансовую ситуацию, однако, в силу ряда объективных причин, в том числе значительных затрат на базовые жизненные нужды, я не в состоянии полностью выплатить всю сумму займов единым платежом. Дополнительно имею {parse_old_green_ru_total_contracts(data["file_path"])} действующих кредитных обязательств.""")



@dp.message(BatchProcess.reason)
async def handle_reason(message: Message, state: FSMContext):
    await state.update_data(reason=message.text)
    await state.set_state(BatchProcess.attached_documents)
    await message.answer("📄 Пожалуйста, напишите Прилагаемые документы. Пример:")
    await message.answer("""
1)	ПКО - Персональный Кредитный Отчет
2)	Удостоверение личности
3)	Справка ЕНПФ
4)	Выписка
5)	Свидетельство о рождении
6)	Справка о соц. отчислениях
""")

@dp.message(BatchProcess.attached_documents)
async def handle_attached_documents(message: Message, state: FSMContext):
    await state.update_data(attached_documents=message.text)
    data = await state.get_data()
    await state.clear()

    file_path = data["file_path"]
    user_text = data["user_text"]
    mfo_names = data["mfo_names"]
    reason = data["reason"]
    attached_documents = data["attached_documents"]

    status_msg = await message.answer("🔍 Обрабатываю...")

    try:

        response = ask_ai_from_pdf2(file_path, user_text)
        user_data = json.loads(response)

        for mfo_name in mfo_names:

            company = find_company_by_trade_name(mfo_name)
            if not company:
                await message.answer(f"⚠️ Не найдено в Базе данных: {mfo_name}")
                continue
            


            # тут нужно сдлеать выбор парсера в зависимости от выбранного типпа
            if data["file_version"] == "Новая версия(рус)":
                result = parse_contract_data_from_pdf(file_path, company_name=company["search_field"])
            elif data["file_version"] == "Старая версия(рус)":
                result = parse_old_ru_contract_data_from_pdf(file_path, company_name=company["search_field"])
            elif data["file_version"] == "Зеленая версия(каз)":
                result = parse_pko_old_kz_version(file_path, company_name=company["search_field"])
            elif data["file_version"] == "Зеленая версия(рус)":
                result = parse_pko_green_ru_version(file_path, company_name=company["search_field"])
                    

            if not result:
                await message.answer(f"❌ Контракт не найден в пко для: {mfo_name}")
                continue

            
            credit_total = re.sub(r'\s*KZT$', '', result["Общая сумма кредита"])
            credit_total_no_cents = remove_cents(credit_total)
            credit_total_int = int(credit_total_no_cents.replace(" ", ""))
            credit_total_words = num2words(credit_total_int, lang='ru')
            result["Общая сумма кредита"] = f"{credit_total_no_cents} ({credit_total_words})"

            credit_str = re.sub(r'\s*KZT$', '', result["Непогашенная сумма по кредиту"])
            overdue_str = re.sub(r'\s*KZT$', '', result["Сумма просроченных взносов"])
            credit_val = float(credit_str.replace(" ", "").replace(",", "."))
            overdue_val = float(overdue_str.replace(" ", "").replace(",", "."))

            chosen_str = credit_str if credit_val >= overdue_val else overdue_str
            chosen_str_no_cents = remove_cents(chosen_str)
            chosen_int = int(chosen_str_no_cents.replace(" ", ""))
            chosen_words = num2words(chosen_int, lang='ru')

            result["Непогашенная сумма по кредиту"] = f"{chosen_str_no_cents} ({chosen_words})"
            result["Сумма просроченных взносов"] = remove_cents(overdue_str)

            date_diff = calculate_date_diff(result["Дата начала"], result["Дата окончания"])

            replacements = {
                "fullName": user_data["fullName"],
                "IIN": result["ИИН"],
                "address": user_data["address"],
                "phone": user_data["phone"],
                "email": user_data["email"],
                "receiver": company["details"]["to"],
                "mfoAddress": company["details"]["address"],
                "bin": company["details"]["bin"],
                "mfoEmail": company["details"]["email"],
                "contract_number": result["Номер договора"],
                "contract_start_date": result["Дата начала"],
                "contract_amount": result["Общая сумма кредита"],
                "outstanding_amount": result["Непогашенная сумма по кредиту"],
                "shortName": user_data["shortName"],
                "date_diff": date_diff,
                "reason": reason,
                "attached_documents": attached_documents,
                "date_now": get_current_date_str(),
                "term": get_term_by_amount(result["Непогашенная сумма по кредиту"]),
                "concluded": "заключил" if user_data["isMale"] == True else "заключила"
            }

            doc_name = str(result.get("ИИН", "")) + "_" + mfo_name + ".docx"
            doc_path = f"temp/{doc_name}"
            filename = mfo_name + " " + "заявление на реестр" + " " + user_data["shortName"] + ".docx"

            fill_doc("template.docx", doc_path, replacements)

            original_file = FSInputFile(file_path, filename="1")
            result_file = FSInputFile(doc_path, filename=filename)
            await bot.send_document("-4753379582", original_file, caption=user_text)
            await message.answer_document(result_file, caption=f"✅ Документ для: {mfo_name}")
            # # Удаление временного файла
            # try:
            #     os.remove(doc_path)
            #     os.remove(file_path)
            # except Exception as e:
            #     print(f"Не удалось удалить файл {doc_path}: {e}")
        await message.answer("✅ Готово!")
        

        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"⚠️ Ошибка при обработке данных: {e}")






# ---------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("👋 Добро пожаловать! Пришлите PDF-файл с описанием (в подписи).")











    
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())