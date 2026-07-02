# ============================================
# bot.py - IMO Shop + АВТОРЕГИСТРАЦИЯ + ЛОГИ
# ============================================

import asyncio
import logging
import os
import json
import re
import sys
from datetime import datetime
from typing import Dict

import aiohttp
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ============================================
# ЛОГИРОВАНИЕ
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def log_step(step: str, data: str = ""):
    """Логирование шагов авторегистрации"""
    msg = f"[STEP] {step}"
    if data:
        msg += f" | {data}"
    logger.info(msg)

def log_api(service: str, method: str, request: str, response: str):
    """Логирование API запросов"""
    logger.info(f"[API] {service}.{method}")
    logger.info(f"  REQ: {request}")
    logger.info(f"  RES: {response}")

def log_error(module: str, error: str):
    """Логирование ошибок"""
    logger.error(f"[ERROR] {module}: {error}")

# ============================================
# НАСТРОЙКИ
# ============================================
BOT_TOKEN = '8724614250:AAGK3KkM1qJWQIu0UqvvhPpEbxViBMHglFI'
ADMIN_IDS = [8632861931,743956377]  # твой ID
SMSFAST_API_KEY = 'Lwx5xNXcAATYznbQmrm6DnkIlwFhAz'
CRYPTOBOT_API_KEY = '590558:AATFDxdtESm34k9IoB2U7TLAo0LQylVdmPo'
MARKUP_PERCENT = 20
USD_RATE = 75
DATA_FILE = 'data.json'
AUTO_REG_PRICE = 0  # Цена авторегистрации в рублях

def get_markup():
    return 1 + (MARKUP_PERCENT / 100)

COUNTRIES = {
    '12': '🇺🇸 США (вирт)',
    '6': '🇮🇩 Индонезия',
    '1': '🇺🇦 Украина',
    '2': '🇰🇿 Казахстан',
    '4': '🇵🇭 Филиппины',
    '22': '🇮🇳 Индия',
    '52': '🇹🇭 Таиланд',
    '31': '🇿🇦 Южная Африка',
    '36': '🇨🇦 Канада',
    '16': '🇬🇧 Великобритания',
}

# ============================================
# IMO БИБЛИОТЕКА
# ============================================
try:
    from imo import Imo
    IMO_AVAILABLE = True
    logger.info("✅ imobot-api успешно импортирован")
except ImportError as e:
    IMO_AVAILABLE = False
    logger.warning(f"⚠️ imobot-api не установлен: {e}")

# ============================================
# ХРАНИЛИЩЕ ДАННЫХ
# ============================================
users = {}
purchases = []
groups = {}
tickets = []

def load_data():
    global users, purchases, groups, tickets
    logger.info(f"[DATA] Загрузка из {DATA_FILE}")
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            users = data.get('users', {})
            purchases = data.get('purchases', [])
            groups = data.get('groups', {})
            tickets = data.get('tickets', [])
        logger.info(f"[DATA] Загружено: users={len(users)}, purchases={len(purchases)}, groups={len(groups)}, tickets={len(tickets)}")
    else:
        logger.info("[DATA] Файл не найден, создаём новый")

def save_data():
    logger.info(f"[DATA] Сохранение: users={len(users)}, purchases={len(purchases)}")
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'users': users,
            'purchases': purchases,
            'groups': groups,
            'tickets': tickets
        }, f, default=str)

def get_user(uid: str) -> dict:
    if uid not in users:
        users[uid] = {
            'balance': 0,
            'total_spent': 0,
            'username': '',
            'is_banned': False,
            'created_at': str(datetime.now())
        }
        logger.info(f"[USER] Создан новый пользователь: {uid}")
        save_data()
    return users[uid]

load_data()

# ============================================
# ВРЕМЕННАЯ ПОЧТА (GuerrillaMail)
# ============================================
class TempMail:
    @staticmethod
    async def create():
        log_step("CREATE_EMAIL", "Создание временной почты")
        try:
            async with aiohttp.ClientSession() as session:
                params = {'f': 'get_email_address', 'lang': 'ru'}
                url = 'https://api.guerrillamail.com/ajax.php'
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    email = data.get('email_addr', '')
                    sid = data.get('sid_token', '')
                    log_api("GuerrillaMail", "create", str(params), f"email={email}, sid={sid}")
                    log_step("CREATE_EMAIL", f"✅ {email}")
                    return {'email': email, 'sid': sid}
        except Exception as e:
            log_error("TempMail.create", str(e))
            return {'email': '', 'sid': ''}

    @staticmethod
    async def check_inbox(sid):
        try:
            async with aiohttp.ClientSession() as session:
                params = {'f': 'get_email_list', 'sid_token': sid, 'offset': 0}
                async with session.get('https://api.guerrillamail.com/ajax.php', params=params) as resp:
                    data = await resp.json()
                    emails = data.get('list', [])
                    if emails:
                        log_step("CHECK_EMAIL", f"Найдено писем: {len(emails)}")
                        for e in emails:
                            logger.info(f"  📧 {e.get('mail_subject', '')}")
                    return emails
        except Exception as e:
            log_error("TempMail.check_inbox", str(e))
            return []

    @staticmethod
    async def get_code(sid, timeout=60):
        log_step("WAIT_CODE", f"Ожидание кода (таймаут {timeout}с)")
        for i in range(timeout // 5):
            await asyncio.sleep(5)
            emails = await TempMail.check_inbox(sid)
            for email in emails:
                subject = email.get('mail_subject', '')
                body = email.get('mail_excerpt', '') + ' ' + email.get('mail_body', '')
                
                # Ищем 6-значный код
                codes = re.findall(r'\b\d{6}\b', body)
                if codes:
                    log_step("FOUND_CODE", f"Код в письме: {codes[0]}")
                    return codes[0]
                
                # Ищем ссылку подтверждения
                links = re.findall(r'https?://[^\s"]+', body)
                for link in links:
                    if any(kw in link.lower() for kw in ['confirm', 'verify', 'code', 'activate']):
                        log_step("FOUND_LINK", f"Ссылка: {link}")
                        return link
            
            if i % 6 == 0 and i > 0:
                log_step("WAIT_CODE", f"Всё ещё ждём... ({i*5} сек)")
        
        log_step("WAIT_CODE", "❌ Таймаут")
        return None

# ============================================
# SMSFAST SERVICE (с логированием)
# ============================================
class SmsFastService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = 'https://smsfastapi.com/stubs/handler_api.php'
    
    async def get_balance(self) -> str:
        params = {'api_key': self.api_key, 'action': 'getBalance'}
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                log_api("SmsFast", "getBalance", str(params), text)
                if 'ACCESS_BALANCE:' in text:
                    return text.split(':')[1]
                return '0'
    
    async def get_price(self, country: str) -> float:
        params = {'api_key': self.api_key, 'action': 'getPrices', 'service': 'im', 'country': country}
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                log_api("SmsFast", "getPrice", f"country={country}", text)
                if 'BAD' in text:
                    return 0
                try:
                    data = json.loads(text)
                    for services in data.values():
                        if 'im' in services:
                            price = float(services['im']['cost'])
                            log_step("GET_PRICE", f"Страна={country}, цена={price}")
                            return price
                except Exception as e:
                    log_error("SmsFast.getPrice", str(e))
        return 0
    
    async def buy_number(self, country: str) -> Dict:
        params = {'api_key': self.api_key, 'action': 'getNumber', 'service': 'im', 'country': country}
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                log_api("SmsFast", "buyNumber", f"country={country}", text)
                if 'ACCESS_NUMBER:' in text:
                    parts = text.split(':')
                    result = {'id': parts[1], 'phone': parts[2]}
                    log_step("BUY_NUMBER", f"✅ {result['phone']} (ID: {result['id']})")
                    return result
                log_error("SmsFast.buyNumber", text)
                return {'error': text}
    
    async def get_sms(self, activation_id: str) -> str:
        params = {'api_key': self.api_key, 'action': 'getStatus', 'id': activation_id}
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                if 'STATUS_OK:' in text:
                    code = text.split(':')[1].strip()
                    log_api("SmsFast", "getSms", f"id={activation_id}", f"КОД: {code}")
                    return code
                elif 'STATUS_WAIT_RETRY:' in text:
                    code = text.split(':')[1].strip()
                    log_api("SmsFast", "getSms", f"id={activation_id}", f"КОД(retry): {code}")
                    return code
        return ''
    
    async def set_status(self, activation_id: str, status: str):
        params = {'api_key': self.api_key, 'action': 'setStatus', 'status': status, 'id': activation_id}
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                log_api("SmsFast", "setStatus", f"id={activation_id}, status={status}", text)
                return text

class CryptoService:
    def __init__(self):
        self.api_key = CRYPTOBOT_API_KEY
        self.base_url = 'https://pay.crypt.bot/api'
    
    async def create_invoice(self, amount_usdt: float, user_id: int) -> Dict:
        headers = {'Content-Type': 'application/json', 'Crypto-Pay-API-Token': self.api_key}
        data = {
            'asset': 'USDT', 'amount': str(amount_usdt),
            'description': 'Пополнение IMO Shop',
            'payload': str(user_id), 'allow_anonymous': False,
            'paid_btn_name': 'callback', 'paid_btn_url': 'https://t.me/imo_shop_bot'
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{self.base_url}/createInvoice', headers=headers, json=data) as resp:
                result = await resp.json()
                log_api("CryptoBot", "createInvoice", str(data), str(result))
                if result.get('ok'):
                    return result.get('result', {})
                return result
    
    async def get_invoice(self, invoice_id: int) -> Dict:
        headers = {'Content-Type': 'application/json', 'Crypto-Pay-API-Token': self.api_key}
        data = {'invoice_ids': str(invoice_id)}
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{self.base_url}/getInvoices', headers=headers, json=data) as resp:
                result = await resp.json()
                log_api("CryptoBot", "getInvoice", str(data), str(result))
                if result.get('ok') and result.get('result', {}).get('items'):
                    return result['result']['items'][0]
                return {}

smsfast_service = SmsFastService(SMSFAST_API_KEY)
crypto_service = CryptoService()

# ============================================
# IMO АВТОРЕГИСТРАЦИЯ (с логированием)
# ============================================
class ImoAutoReg:
    @staticmethod
    async def full_registration(phone: str, sms_code: str) -> Dict:
        """Полный цикл регистрации IMO"""
        log_step("IMO_REG", f"Начало регистрации: {phone}")
        
        if not IMO_AVAILABLE:
            log_error("IMO_REG", "Библиотека не установлена")
            return {'success': False, 'error': 'imo библиотека не установлена'}
        
        try:
            # Шаг 1: Создаём временную почту
            log_step("IMO_REG", "Шаг 1: Создание почты")
            mail = await TempMail.create()
            email = mail['email']
            sid = mail['sid']
            log_step("IMO_REG", f"Почта создана: {email}")
            
            # Шаг 2: Регистрируем номер в IMO
            log_step("IMO_REG", "Шаг 2: Отправка номера в IMO")
            imo = Imo()
            
            result = await asyncio.to_thread(imo.register, phone)
            log_step("IMO_REG", f"Ответ IMO: {result}")
            
            if not result.get('success'):
                return {'success': False, 'error': result.get('error', 'Ошибка регистрации')}
            
            # Шаг 3: Подтверждаем SMS код
            log_step("IMO_REG", f"Шаг 3: Подтверждение кода: {sms_code}")
            verify = await asyncio.to_thread(imo.verify_code, sms_code)
            log_step("IMO_REG", f"Ответ верификации: {verify}")
            
            if verify.get('success'):
                # Шаг 4: Ждём письмо с подтверждением (если нужно)
                log_step("IMO_REG", "Шаг 4: Ожидание письма подтверждения")
                email_code = await TempMail.get_code(sid, timeout=30)
                
                if email_code:
                    log_step("IMO_REG", f"Код из письма: {email_code}")
                
                log_step("IMO_REG", "✅ Регистрация завершена!")
                return {
                    'success': True,
                    'phone': phone,
                    'sms_code': sms_code,
                    'email': email,
                    'email_code': email_code
                }
            
            log_error("IMO_REG", f"Ошибка верификации: {verify.get('error')}")
            return {'success': False, 'error': verify.get('error', 'Ошибка верификации')}
            
        except Exception as e:
            log_error("IMO_REG", str(e))
            return {'success': False, 'error': str(e)}

# ============================================
# KEYBOARDS
# ============================================
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Купить IMO", callback_data="buy_imo")
    builder.button(text="🤖 Авторегистрация", callback_data="auto_reg")
    builder.button(text="📱 Мои аккаунты", callback_data="my_accounts")
    builder.button(text="👤 Профиль", callback_data="my_profile")
    builder.button(text="💎 Пополнить", callback_data="top_up")
    builder.button(text="💬 Поддержка", callback_data="support")
    builder.adjust(2)
    return builder.as_markup()

def back_button(data):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data=data)
    return builder.as_markup()

# ============================================
# HANDLERS
# ============================================
user_router = Router()

class UserStates(StatesGroup):
    waiting_for_support = State()

@user_router.message(Command('start'))
async def cmd_start(message: Message):
    uid = str(message.from_user.id)
    user = get_user(uid)
    user['username'] = message.from_user.username or ''
    save_data()
    log_step("START", f"Пользователь {uid}")
    
    imo_status = "✅ Доступна" if IMO_AVAILABLE else "❌ Отключена"
    
    await message.answer(
        f"✨ <b>IMO Shop</b>\n\n"
        f"🛒 Покупка номеров IMO\n"
        f"🤖 Авторегистрация: {imo_status}\n"
        f"💎 Пополнение через CryptoBot\n\n"
        f"<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

@user_router.callback_query(F.data == "auto_reg")
async def auto_reg_info(callback: CallbackQuery):
    log_step("MENU", "Открыта страница авторегистрации")
    
    if not IMO_AVAILABLE:
        await callback.answer("❌ Авторегистрация отключена", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🤖 <b>Авторегистрация IMO</b>\n\n"
        "Бот автоматически:\n"
        "1. Купит номер телефона\n"
        "2. Создаст временную почту\n"
        "3. Зарегистрирует аккаунт IMO\n"
        "4. Выдаст вам готовые данные\n\n"
        f"💰 Стоимость: <b>{AUTO_REG_PRICE}₽</b>\n\n"
        "<i>Начать?</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder()
            .button(text="✅ Начать", callback_data="start_auto_reg")
            .button(text="🔙 Назад", callback_data="main_menu")
            .adjust(1).as_markup()
    )
    await callback.answer()

@user_router.callback_query(F.data == "start_auto_reg")
async def start_auto_reg(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    user = get_user(uid)
    
    log_step("AUTO_REG", f"Запуск для пользователя {uid}")
    
    if user['balance'] < AUTO_REG_PRICE:
        log_step("AUTO_REG", f"Недостаточно средств: {user['balance']} < {AUTO_REG_PRICE}")
        await callback.message.edit_text(
            f"❌ Недостаточно средств!\n💰 Нужно: {AUTO_REG_PRICE}₽\n💳 Баланс: {user['balance']:.2f}₽",
            reply_markup=back_button("auto_reg")
        )
        await callback.answer()
        return
    
    msg = await callback.message.edit_text("🔄 <b>Запускаю авторегистрацию...</b>", parse_mode="HTML")
    
    try:
        # Шаг 1: Покупаем номер
        log_step("AUTO_REG", "Шаг 1: Покупка номера")
        await msg.edit_text("📱 <b>Покупаю номер...</b>", parse_mode="HTML")
        
        number = await smsfast_service.buy_number('12')
        
        if 'error' in number:
            log_error("AUTO_REG", f"Ошибка покупки: {number['error']}")
            await msg.edit_text(f"❌ Ошибка покупки: {number['error']}")
            await callback.answer()
            return
        
        phone = number['phone']
        order_id = number['id']
        
        # Шаг 2: Запускаем регистрацию IMO
        log_step("AUTO_REG", f"Шаг 2: Регистрация {phone}")
        await msg.edit_text(f"📤 <b>Регистрирую {phone}...</b>", parse_mode="HTML")
        
        # Создаём почту
        mail = await TempMail.create()
        
        # Отправляем в IMO
        imo = Imo()
        result = await asyncio.to_thread(imo.register, phone)
        log_step("AUTO_REG", f"IMO response: {result}")
        
        if not result.get('success'):
            await msg.edit_text(f"❌ Ошибка IMO: {result.get('error')}")
            await callback.answer()
            return
        
        # Ждём SMS
        await msg.edit_text("⏳ <b>Жду SMS код...</b>", parse_mode="HTML")
        
        sms_code = None
        for i in range(60):
            await asyncio.sleep(2)
            sms_code = await smsfast_service.get_sms(order_id)
            if sms_code:
                log_step("AUTO_REG", f"SMS получен: {sms_code}")
                break
            if i % 15 == 0 and i > 0:
                await msg.edit_text(f"⏳ <b>Всё ещё жду SMS...</b> ({i*2} сек)", parse_mode="HTML")
        
        if not sms_code:
            log_error("AUTO_REG", "SMS не получен за 2 минуты")
            await msg.edit_text("❌ SMS не получен за 2 минуты")
            await callback.answer()
            return
        
        # Подтверждаем код
        await msg.edit_text(f"🔑 <b>Подтверждаю код...</b>\n<code>{sms_code}</code>", parse_mode="HTML")
        
        verify = await asyncio.to_thread(imo.verify_code, sms_code)
        log_step("AUTO_REG", f"Verify: {verify}")
        
        if verify.get('success'):
            # Списываем деньги
            user['balance'] -= AUTO_REG_PRICE
            user['total_spent'] += AUTO_REG_PRICE
            
            # Сохраняем
            purchases.append({
                'user_id': uid,
                'type': 'auto_reg',
                'phone': phone,
                'sms_code': sms_code,
                'email': mail['email'],
                'price_rub': AUTO_REG_PRICE,
                'status': 'completed',
                'created_at': str(datetime.now())
            })
            save_data()
            
            log_step("AUTO_REG", f"✅ Успешно! {phone}")
            
            await msg.edit_text(
                f"✅ <b>Аккаунт IMO создан!</b>\n\n"
                f"📱 Номер: <code>{phone}</code>\n"
                f"🔑 Код SMS: <code>{sms_code}</code>\n"
                f"📧 Почта: <code>{mail['email']}</code>\n"
                f"💰 Списано: <b>{AUTO_REG_PRICE}₽</b>\n\n"
                f"<i>Данные сохранены в «Мои аккаунты»</i>",
                parse_mode="HTML",
                reply_markup=back_button("main_menu")
            )
        else:
            log_error("AUTO_REG", f"Ошибка верификации: {verify.get('error')}")
            await msg.edit_text(f"❌ Ошибка: {verify.get('error')}")
        
    except Exception as e:
        log_error("AUTO_REG", str(e))
        await msg.edit_text(f"❌ Ошибка: {e}")
    
    await callback.answer()

@user_router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    await callback.message.edit_text("✨ <b>IMO Shop</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

# ============================================
# BOT
# ============================================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(user_router)

async def main():
    logger.info("="*50)
    logger.info("БОТ ЗАПУЩЕН")
    logger.info(f"IMO библиотека: {'✅' if IMO_AVAILABLE else '❌'}")
    logger.info(f"Пользователей: {len(users)}")
    logger.info(f"Покупок: {len(purchases)}")
    logger.info("="*50)
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
