# ============================================
# bot.py - IMO Shop (smsfast + CryptoBot)
# ============================================

import asyncio
import logging
import os
import json
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
# НАСТРОЙКИ
# ============================================
BOT_TOKEN = '8724614250:AAGK3KkM1qJWQIu0UqvvhPpEbxViBMHglFI'
ADMIN_IDS = [8632861931,743956377]  # твой ID
SMSFAST_API_KEY = 'Lwx5xNXcAATYznbQmrm6DnkIlwFhAz'
CRYPTOBOT_API_KEY = '590558:AATFDxdtESm34k9IoB2U7TLAo0LQylVdmPo'
MARKUP_PERCENT = 20
USD_RATE = 75
DATA_FILE = 'data.json'

def get_markup():
    return 1 + (MARKUP_PERCENT / 100)

COUNTRIES = {
    '6': '🇮🇩 Индонезия',
    '12': '🇺🇸 США (вирт)',
    '1': '🇺🇦 Украина',
    '2': '🇰🇿 Казахстан',
    '4': '🇵🇭 Филиппины',
    '22': '🇮🇳 Индия',
    '52': '🇹🇭 Таиланд',
    '31': '🇿🇦 Южная Африка',
    '36': '🇨🇦 Канада',
    '16': '🇬🇧 Великобритания',
    '187': '🇺🇸 США',
    '21': '🇪🇬 Египет',
    '62': '🇹🇷 Турция',
    '73': '🇧🇷 Бразилия',
    '43': '🇩🇪 Германия',
    '78': '🇫🇷 Франция',
    '48': '🇳🇱 Нидерланды',
    '10': '🇻🇳 Вьетнам',
    '60': '🇧🇩 Бангладеш',
    '19': '🇳🇬 Нигерия',
}

# ============================================
# ХРАНИЛИЩЕ ДАННЫХ (JSON)
# ============================================
users = {}
purchases = []
groups = {}
tickets = []
transactions = []

def load_data():
    global users, purchases, groups, tickets, transactions
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            users = data.get('users', {})
            purchases = data.get('purchases', [])
            groups = data.get('groups', {})
            tickets = data.get('tickets', [])
            transactions = data.get('transactions', [])

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'users': users,
            'purchases': purchases,
            'groups': groups,
            'tickets': tickets,
            'transactions': transactions
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
        save_data()
    return users[uid]

load_data()

# ============================================
# service
# ============================================
class SmsFastService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = 'https://smsfastapi.com/stubs/handler_api.php'
    
    async def get_balance(self) -> str:
        async with aiohttp.ClientSession() as session:
            params = {'api_key': self.api_key, 'action': 'getBalance'}
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                logger.info(f"[getBalance] Ответ: {text}")
                if 'ACCESS_BALANCE:' in text:
                    return text.split(':')[1]
                return '0'
    
    async def get_price(self, country: str) -> float:
        async with aiohttp.ClientSession() as session:
            params = {'api_key': self.api_key, 'action': 'getPrices', 'service': 'im', 'country': country}
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                logger.info(f"[getPrice] Страна {country}: {text}")
                if 'BAD' in text:
                    return 0
                try:
                    data = json.loads(text)
                    for c, services in data.items():
                        if 'im' in services:
                            cost = float(services['im']['cost'])
                            logger.info(f"[getPrice] Найдена цена: {cost}")
                            return cost
                except Exception as e:
                    logger.error(f"[getPrice] Ошибка парсинга: {e}")
        return 0
    
    async def buy_number(self, country: str) -> Dict:
        async with aiohttp.ClientSession() as session:
            params = {'api_key': self.api_key, 'action': 'getNumber', 'service': 'im', 'country': country}
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                logger.info(f"[buyNumber] Страна {country}: {text}")
                if 'ACCESS_NUMBER:' in text:
                    parts = text.split(':')
                    result = {'id': parts[1], 'phone': parts[2]}
                    logger.info(f"[buyNumber] Успех: ID={parts[1]}, phone={parts[2]}")
                    return result
                logger.error(f"[buyNumber] Ошибка: {text}")
                return {'error': text}
    
    async def get_sms(self, activation_id: str) -> str:
        async with aiohttp.ClientSession() as session:
            params = {'api_key': self.api_key, 'action': 'getStatus', 'id': activation_id}
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                logger.info(f"[getStatus] ID={activation_id}: {text}")
                if 'STATUS_OK:' in text:
                    code = text.split(':')[1]
                    logger.info(f"[getStatus] КОД ПОЛУЧЕН: {code}")
                    return code
                elif 'STATUS_WAIT_CODE' in text:
                    logger.info(f"[getStatus] Ожидание кода...")
                elif 'STATUS_CANCEL' in text:
                    logger.info(f"[getStatus] Активация отменена")
                elif 'NO_ACTIVATION' in text:
                    logger.info(f"[getStatus] Активация не найдена")
        return ''
    
    async def set_status(self, activation_id: str, status: str):
        async with aiohttp.ClientSession() as session:
            params = {'api_key': self.api_key, 'action': 'setStatus', 'status': status, 'id': activation_id}
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                logger.info(f"[setStatus] ID={activation_id}, status={status}: {text}")
                return text
    
    async def cancel_order(self, activation_id: str):
        return await self.set_status(activation_id, '8')

class CryptoService:
    def __init__(self):
        self.api_key = CRYPTOBOT_API_KEY
        self.base_url = 'https://pay.crypt.bot/api'
    
    async def create_invoice(self, amount_usdt: float, user_id: int) -> Dict:
        async with aiohttp.ClientSession() as session:
            headers = {
                'Content-Type': 'application/json',
                'Crypto-Pay-API-Token': self.api_key
            }
            data = {
                'asset': 'USDT',
                'amount': str(amount_usdt),
                'description': 'Пополнение баланса IMO Shop',
                'payload': str(user_id),
                'allow_anonymous': False,
                'paid_btn_name': 'callback',
                'paid_btn_url': 'https://t.me/imo_shop_bot'
            }
            async with session.post(f'{self.base_url}/createInvoice', headers=headers, json=data) as resp:
                result = await resp.json()
                logger.info(f"[CryptoBot] createInvoice: {result}")
                if result.get('ok'):
                    return result.get('result', {})
                return result
    
    async def get_invoice(self, invoice_id: int) -> Dict:
        async with aiohttp.ClientSession() as session:
            headers = {
                'Content-Type': 'application/json',
                'Crypto-Pay-API-Token': self.api_key
            }
            data = {'invoice_ids': str(invoice_id)}
            async with session.post(f'{self.base_url}/getInvoices', headers=headers, json=data) as resp:
                result = await resp.json()
                logger.info(f"[CryptoBot] getInvoice: {result}")
                if result.get('ok') and result.get('result', {}).get('items'):
                    return result['result']['items'][0]
                return {}

smsfast_service = SmsFastService(SMSFAST_API_KEY)
crypto_service = CryptoService()

# ============================================
# keyboards
# ============================================
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Купить IMO", callback_data="buy_imo")
    builder.button(text="📱 Мои аккаунты", callback_data="my_accounts")
    builder.button(text="👤 Мой профиль", callback_data="my_profile")
    builder.button(text="📋 Мои покупки", callback_data="my_purchases")
    builder.button(text="💰 Пополнить баланс", callback_data="top_up")
    builder.button(text="💬 Поддержка", callback_data="support")
    builder.adjust(2)
    return builder.as_markup()

def back_button(data):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data=data)
    return builder.as_markup()

def get_admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Баланс smsfas", callback_data="admin_balance")
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="💵 Начислить", callback_data="admin_add_balance")
    builder.button(text="💸 Списать", callback_data="admin_remove_balance")
    builder.button(text="🚫 Бан/Разбан", callback_data="admin_ban")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="🎫 Тикеты", callback_data="admin_tickets")
    builder.button(text="👥 Группы", callback_data="admin_groups")
    builder.button(text="💲 Наценка", callback_data="admin_markup")
    builder.button(text="💱 Курс USD", callback_data="admin_usd_rate")
    builder.button(text="🔙 Выйти", callback_data="admin_exit")
    builder.adjust(2)
    return builder.as_markup()

def get_quantity_keyboard(price_rub, country):
    builder = InlineKeyboardBuilder()
    for qty in [1, 2, 3, 5, 10]:
        total = round(price_rub * qty, 2)
        builder.button(text=f"{qty} шт — {total}₽", callback_data=f"qty_{qty}_{price_rub}_{country}")
    builder.button(text="🔙 Назад", callback_data="buy_imo")
    builder.adjust(2)
    return builder.as_markup()

def get_countries_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Самая дешёвая (Индонезия)", callback_data="country_6")
    for code, name in COUNTRIES.items():
        if code != '6':
            builder.button(text=name, callback_data=f"country_{code}")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2)
    return builder.as_markup()

# ============================================
# user handlers
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
    await message.answer("👋 Добро пожаловать в IMO Shop!\n\nПокупайте IMO аккаунты.\nБаланс в рублях, пополнение в USDT.", reply_markup=get_main_keyboard())

@user_router.callback_query(F.data == "buy_imo")
async def buy_imo(callback: CallbackQuery):
    await callback.message.edit_text("🛒 Выберите страну:", reply_markup=get_countries_keyboard())
    await callback.answer()

@user_router.callback_query(F.data.startswith("country_"))
async def select_country(callback: CallbackQuery):
    country = callback.data.replace("country_", "")
    await callback.message.edit_text("🔍 Получаю цену...")
    
    api_price = await smsfast_service.get_price(country)
    
    if api_price <= 0:
        await callback.message.edit_text("❌ Нет номеров.", reply_markup=back_button("buy_imo"))
        await callback.answer()
        return
    
    price_rub = round(api_price * get_markup(), 2)
    name = COUNTRIES.get(country, f"Страна {country}")
    
    await callback.message.edit_text(
        f"🛒 {name}\n💰 {price_rub}₽/шт\n\nВыберите количество:",
        reply_markup=get_quantity_keyboard(price_rub, country)
    )
    await callback.answer()

@user_router.callback_query(F.data.startswith("qty_"))
async def process_quantity(callback: CallbackQuery):
    _, qty, price_per_one, country = callback.data.split("_")
    qty = int(qty)
    price_per_one = float(price_per_one)
    total_price = round(price_per_one * qty, 2)
    
    uid = str(callback.from_user.id)
    user = get_user(uid)
    
    logger.info(f"[ПОКУПКА] Пользователь {uid}, страна {country}, кол-во {qty}, цена {price_per_one}")
    
    if user['balance'] < total_price:
        await callback.message.edit_text(
            f"❌ Недостаточно средств!\n{qty} шт × {price_per_one}₽ = {total_price}₽\nБаланс: {user['balance']:.2f}₽",
            reply_markup=back_button("buy_imo")
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(f"🔄 Покупаю {qty} шт...")
    
    success = []
    failed = 0
    
    for i in range(qty):
        result = await smsfast_service.buy_number(country)
        
        if result.get('id') and 'error' not in result:
            order_id = result['id']
            phone = result['phone']
            
            user['balance'] -= price_per_one
            user['total_spent'] += price_per_one
            
            purchases.append({
                'user_id': uid,
                'country': COUNTRIES.get(country, country),
                'phone': phone,
                'order_id': order_id,
                'sms_code': '',
                'price_rub': price_per_one,
                'status': 'waiting',
                'created_at': str(datetime.now())
            })
            transactions.append({
                'user_id': uid,
                'type': 'purchase',
                'amount': -price_per_one,
                'description': 'IMO',
                'created_at': str(datetime.now())
            })
            save_data()
            
            success.append({'phone': phone, 'order_id': order_id})
        else:
            failed += 1
    
    if not success:
        await callback.message.edit_text("❌ Все покупки не удались.", reply_markup=back_button("buy_imo"))
        await callback.answer()
        return
    
    text = f"✅ Куплено: {len(success)}/{qty}\nЦена: {price_per_one}₽/шт\n💰 Баланс: {user['balance']:.2f}₽\n\n📱 Номера:\n"
    for s in success:
        text += f"{s['phone']}\n"
    text += "\nУправление в разделе «Мои аккаунты»"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Мои аккаунты", callback_data="my_accounts")
    builder.button(text="🛒 Купить ещё", callback_data="buy_imo")
    builder.button(text="🔙 В меню", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@user_router.callback_query(F.data == "my_accounts")
async def my_accounts(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    my_purchases = [p for p in purchases if p['user_id'] == uid and p.get('status') != 'cancelled']
    
    if not my_purchases:
        await callback.message.edit_text("📱 У вас нет активных аккаунтов.", reply_markup=back_button("main_menu"))
        await callback.answer()
        return
    
    text = "📱 Мои аккаунты:\n\n"
    builder = InlineKeyboardBuilder()
    
    for p in reversed(my_purchases):
        status_text = "✅" if p.get('sms_code') else "⏳"
        text += f"{status_text} {p['phone']} | {p.get('country','')} | {p['price_rub']}₽\n"
        if p.get('sms_code'):
            text += f"   Код: {p['sms_code']}\n"
        
        if not p.get('sms_code'):
            builder.button(text=f"📩 Код: {p['phone']}", callback_data=f"sms_{p['order_id']}")
            builder.button(text=f"🔄 Повтор: {p['phone']}", callback_data=f"resend_{p['order_id']}")
        else:
            builder.button(text=f"🔄 Обновить: {p['phone']}", callback_data=f"resend_{p['order_id']}")
    
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@user_router.callback_query(F.data.startswith("sms_"))
async def get_sms_code(callback: CallbackQuery):
    order_id = callback.data.replace("sms_", "")
    
    await callback.message.edit_text("⏳ Ожидаю SMS...\n\nВведите номер в приложении IMO и запросите код.")
    
    for _ in range(60):
        await asyncio.sleep(2)
        code = await smsfast_service.get_sms(order_id)
        if code:
            for p in purchases:
                if p.get('order_id') == order_id:
                    p['sms_code'] = code
                    p['status'] = 'completed'
                    save_data()
                    break
            
            await callback.message.edit_text(
                f"✅ Код получен!\n\n💬 Код: {code}\n\nВведите его в приложении IMO.",
                reply_markup=back_button("my_accounts")
            )
            await callback.answer()
            return
    
    await callback.message.edit_text("❌ Код не получен за 2 минуты.\nНажмите «Повтор SMS» или попробуйте позже.", reply_markup=back_button("my_accounts"))
    await callback.answer()

@user_router.callback_query(F.data.startswith("resend_"))
async def resend_sms(callback: CallbackQuery):
    order_id = callback.data.replace("resend_", "")
    
    await smsfast_service.set_status(order_id, '3')
    
    await callback.message.edit_text("🔄 Повторная отправка SMS...\n\nОжидаю код...")
    
    for _ in range(60):
        await asyncio.sleep(2)
        code = await smsfast_service.get_sms(order_id)
        if code:
            for p in purchases:
                if p.get('order_id') == order_id:
                    p['sms_code'] = code
                    p['status'] = 'completed'
                    save_data()
                    break
            
            await callback.message.edit_text(
                f"✅ Код получен!\n\n💬 Код: {code}",
                reply_markup=back_button("my_accounts")
            )
            await callback.answer()
            return
    
    await callback.message.edit_text("❌ Код не получен.", reply_markup=back_button("my_accounts"))
    await callback.answer()

@user_router.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    user = get_user(uid)
    
    my_purchases = [p for p in purchases if p['user_id'] == uid][-5:]
    
    text = f"👤 Профиль\n\nID: {uid}\n💰 Баланс: {user['balance']:.2f}₽\n💸 Потрачено: {user['total_spent']:.2f}₽\n📱 Покупок: {len([p for p in purchases if p['user_id'] == uid])}"
    if my_purchases:
        text += "\n\nПоследние:\n"
        for p in reversed(my_purchases):
            text += f"• {p.get('country','')} | {p['phone']} — {p['price_rub']}₽\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Пополнить", callback_data="top_up")
    builder.button(text="📱 Мои аккаунты", callback_data="my_accounts")
    builder.button(text="📋 Все покупки", callback_data="my_purchases")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@user_router.callback_query(F.data == "my_purchases")
async def my_purchases(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    my_purchases = [p for p in purchases if p['user_id'] == uid][-20:]
    
    text = "📋 История:\n\n" if my_purchases else "📋 Нет покупок."
    for p in reversed(my_purchases):
        code = p.get('sms_code', 'ожидает')
        text += f"{p.get('country','')} | 📱 {p['phone']}\n💬 {code} | 💰 {p['price_rub']}₽\n📅 {p['created_at'][:19]}\n\n"
    
    await callback.message.edit_text(text, reply_markup=back_button("my_profile"))
    await callback.answer()

@user_router.callback_query(F.data == "top_up")
async def top_up(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    for amount_usdt in [1, 2, 5, 10, 20, 50]:
        rub = round(amount_usdt * USD_RATE)
        builder.button(text=f"{amount_usdt} USDT (~{rub}₽)", callback_data=f"amount_{amount_usdt}")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2)
    await callback.message.edit_text(f"💰 Пополнение баланса\n\nБаланс в рублях\nПополнение в USDT\nКурс: 1 USDT ≈ {USD_RATE}₽\n\nВыберите сумму:", reply_markup=builder.as_markup())
    await callback.answer()

@user_router.callback_query(F.data.startswith("amount_"))
async def create_invoice(callback: CallbackQuery):
    amount_usdt = float(callback.data.replace("amount_", ""))
    
    try:
        invoice = await crypto_service.create_invoice(amount_usdt, callback.from_user.id)
        
        if 'pay_url' not in invoice:
            await callback.message.edit_text(f"❌ Ошибка создания счёта:\n{invoice}", reply_markup=back_button("top_up"))
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        builder.button(text="💎 Оплатить", url=invoice['pay_url'])
        builder.button(text="🔄 Проверить оплату", callback_data=f"check_{invoice['invoice_id']}")
        builder.button(text="🔙 Назад", callback_data="top_up")
        builder.adjust(1)
        
        await callback.message.edit_text(
            f"💳 Счёт #{invoice['invoice_id']}\n\n"
            f"Сумма: {amount_usdt} USDT\n"
            f"На баланс: ~{round(amount_usdt * USD_RATE)}₽\n\n"
            f"Нажмите Оплатить 👇\n⏱ 30 мин",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ {str(e)}", reply_markup=back_button("top_up"))
    await callback.answer()

@user_router.callback_query(F.data.startswith("check_"))
async def check_invoice(callback: CallbackQuery):
    invoice_id = int(callback.data.replace("check_", ""))
    
    try:
        invoice = await crypto_service.get_invoice(invoice_id)
        
        if not invoice:
            await callback.answer("Счёт не найден", show_alert=True)
            return
        
        if invoice.get('status') == 'paid':
            uid = str(callback.from_user.id)
            user = get_user(uid)
            
            amount_usdt = float(invoice['amount'])
            amount_rub = round(amount_usdt * USD_RATE, 2)
            user['balance'] += amount_rub
            
            transactions.append({
                'user_id': uid,
                'type': 'deposit',
                'amount': amount_rub,
                'description': f'Пополнение #{invoice_id} ({amount_usdt} USDT)',
                'invoice_id': invoice_id,
                'created_at': str(datetime.now())
            })
            save_data()
            
            await callback.message.edit_text(
                f"✅ Оплачено!\n\nСчёт #{invoice_id}\nСумма: {amount_usdt} USDT\nЗачислено: +{amount_rub}₽\n💰 Баланс: {user['balance']:.2f}₽",
                reply_markup=back_button("main_menu")
            )
        elif invoice.get('status') == 'active':
            await callback.answer("⏳ Счёт ещё не оплачен", show_alert=True)
        else:
            await callback.message.edit_text("❌ Счёт просрочен.", reply_markup=back_button("top_up"))
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
    await callback.answer()

@user_router.callback_query(F.data == "support")
async def support(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("💬 Опишите проблему:", reply_markup=back_button("main_menu"))
    await state.set_state(UserStates.waiting_for_support)
    await callback.answer()

@user_router.message(UserStates.waiting_for_support)
async def process_support(message: Message, state: FSMContext):
    tickets.append({
        'id': len(tickets) + 1,
        'user_id': str(message.from_user.id),
        'message': message.text,
        'status': 'open',
        'created_at': str(datetime.now())
    })
    save_data()
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, f"📨 Тикет #{tickets[-1]['id']}\nОт: {message.from_user.id}\n\n{message.text}")
        except:
            pass
    await message.answer(f"✅ #{tickets[-1]['id']} принято", reply_markup=get_main_keyboard())
    await state.clear()

@user_router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    await callback.message.edit_text("👋 IMO Shop", reply_markup=get_main_keyboard())
    await callback.answer()

# ============================================
# group handlers
# ============================================
group_router = Router()

@group_router.message(Command('connect'))
async def connect_group(message: Message):
    if message.chat.type != 'private':
        return
    
    try:
        group_id = str(int(message.text.split()[1]))
    except:
        await message.answer("❌ /connect [ID группы]")
        return
    
    if group_id in groups:
        await message.answer("❌ Уже подключена.")
        return
    
    groups[group_id] = {
        'owner_id': str(message.from_user.id),
        'created_at': str(datetime.now())
    }
    save_data()
    
    user = get_user(str(message.from_user.id))
    
    await message.answer(f"✅ Группа подключена!\n\nУчастники: /buy\nСписание с вас.\n💰 Баланс: {user['balance']:.2f}₽")

@group_router.message(Command('buy'))
async def buy_in_group(message: Message):
    if message.chat.type == 'private':
        return
    
    group_id = str(message.chat.id)
    
    if group_id not in groups:
        await message.answer("❌ Группа не подключена.")
        return
    
    owner = get_user(groups[group_id]['owner_id'])
    if owner['balance'] <= 0:
        await message.answer("❌ Покупки недоступны.")
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Индонезия", callback_data=f"g_6_{message.chat.id}")
    for code in list(COUNTRIES.keys())[:6]:
        if code != '6':
            builder.button(text=COUNTRIES[code], callback_data=f"g_{code}_{message.chat.id}")
    builder.adjust(2)
    
    await message.answer("🛒 Выберите страну:", reply_markup=builder.as_markup())

@group_router.callback_query(F.data.startswith("g_"))
async def group_purchase(callback: CallbackQuery):
    parts = callback.data.split("_")
    country = parts[1]
    group_id = str(parts[2])
    
    if group_id not in groups:
        await callback.answer("Группа не подключена.")
        return
    
    owner = get_user(groups[group_id]['owner_id'])
    
    api_price = await smsfast_service.get_price(country)
    if api_price <= 0:
        await callback.answer("Нет номеров.")
        return
    
    price_rub = round(api_price * get_markup(), 2)
    
    if owner['balance'] < price_rub:
        await callback.answer("Недостаточно средств.")
        return
    
    result = await smsfast_service.buy_number(country)
    
    if result.get('id') and 'error' not in result:
        order_id = result['id']
        phone = result['phone']
        
        owner['balance'] -= price_rub
        owner['total_spent'] += price_rub
        
        purchases.append({
            'user_id': str(callback.from_user.id),
            'country': COUNTRIES.get(country, country),
            'phone': phone,
            'order_id': order_id,
            'sms_code': '',
            'price_rub': price_rub,
            'status': 'waiting',
            'group_id': group_id,
            'group_owner_id': groups[group_id]['owner_id'],
            'created_at': str(datetime.now())
        })
        save_data()
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📩 Получить код", callback_data=f"sms_{order_id}")
        
        await callback.message.edit_text(
            f"✅ Куплено!\n📱 {phone}\n💰 {price_rub}₽\n\nНажмите кнопку чтобы получить код после запроса SMS в IMO.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    else:
        await callback.answer("Ошибка покупки.")

# ============================================
# admin handlers
# ============================================
admin_router = Router()

class AdminStates(StatesGroup):
    waiting_for_add_balance = State()
    waiting_for_remove_balance = State()
    waiting_for_ban = State()
    waiting_for_broadcast = State()
    waiting_for_markup = State()
    waiting_for_usd_rate = State()
    waiting_for_ticket_response = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@admin_router.message(Command('admin'))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🔧 Админ-панель", reply_markup=get_admin_keyboard())

@admin_router.callback_query(F.data == "admin_balance")
async def admin_balance(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    try:
        bal = await smsfast_service.get_balance()
        price = await smsfast_service.get_price('6')
        price_rub = round(price * get_markup(), 2) if price else 0
        text = f"💰 Баланс smsfas\n\n🟢 {bal}₽\n\n📱 IMO (Индонезия): {price_rub}₽\n💱 Курс: 1 USDT = {USD_RATE}₽"
    except:
        text = "💰 Баланс smsfas\n\n❌ Ошибка"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="admin_balance")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@admin_router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    text = f"👥 Пользователи ({len(users)}):\n\n"
    for uid, u in list(users.items())[:20]:
        status = "🟢" if not u.get('is_banned') else "🚫"
        text += f"{status} {uid} | @{u.get('username', 'нет')} | {u['balance']:.2f}₽\n"
    
    await callback.message.edit_text(text, reply_markup=back_button("admin_back"))
    await callback.answer()

@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    today = str(datetime.now().date())
    today_purchases = [p for p in purchases if p['created_at'][:10] == today]
    
    text = (
        f"📊 Статистика\n\n"
        f"👥 Пользователей: {len(users)}\n"
        f"👥 Групп: {len(groups)}\n\n"
        f"🛒 Сегодня: {len(today_purchases)} шт / {sum(p['price_rub'] for p in today_purchases):.2f}₽\n"
        f"🛒 Всего: {len(purchases)} шт / {sum(p['price_rub'] for p in purchases):.2f}₽\n\n"
        f"💲 Наценка: {MARKUP_PERCENT}%\n"
        f"💱 Курс USDT: {USD_RATE}₽"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="admin_stats")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@admin_router.callback_query(F.data == "admin_add_balance")
async def admin_add_balance(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("💵 ID и сумма в рублях:\n123456789 1000", reply_markup=back_button("admin_back"))
    await state.set_state(AdminStates.waiting_for_add_balance)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_add_balance)
async def process_add_balance(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_id, amount = message.text.split()
        amount = float(amount)
        uid = str(user_id)
        
        user = get_user(uid)
        user['balance'] += amount
        
        transactions.append({
            'user_id': uid,
            'type': 'deposit',
            'amount': amount,
            'description': 'Админ',
            'created_at': str(datetime.now())
        })
        save_data()
        
        await message.answer(f"✅ +{amount}₽ пользователю {user_id}\nБаланс: {user['balance']:.2f}₽")
        try:
            await message.bot.send_message(int(user_id), f"💰 +{amount}₽\nБаланс: {user['balance']:.2f}₽")
        except:
            pass
    except:
        await message.answer("❌ Формат: ID СУММА")
    
    await state.clear()

@admin_router.callback_query(F.data == "admin_remove_balance")
async def admin_remove_balance(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("💸 ID и сумма:", reply_markup=back_button("admin_back"))
    await state.set_state(AdminStates.waiting_for_remove_balance)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_remove_balance)
async def process_remove_balance(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_id, amount = message.text.split()
        amount = float(amount)
        uid = str(user_id)
        
        if uid in users:
            if users[uid]['balance'] >= amount:
                users[uid]['balance'] -= amount
                save_data()
                await message.answer(f"✅ -{amount}₽ у {user_id}\nОстаток: {users[uid]['balance']:.2f}₽")
            else:
                await message.answer(f"❌ Баланс: {users[uid]['balance']:.2f}₽")
        else:
            await message.answer("❌ Не найден.")
    except:
        await message.answer("❌ Формат: ID СУММА")
    
    await state.clear()

@admin_router.callback_query(F.data == "admin_ban")
async def admin_ban(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🚫 ID:", reply_markup=back_button("admin_back"))
    await state.set_state(AdminStates.waiting_for_ban)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_ban)
async def process_ban(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    uid = message.text.strip()
    if uid in users:
        users[uid]['is_banned'] = not users[uid].get('is_banned', False)
        save_data()
        status = "заблокирован" if users[uid]['is_banned'] else "разблокирован"
        await message.answer(f"✅ {uid} {status}.")
    else:
        await message.answer("❌ Не найден.")
    
    await state.clear()

@admin_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("📢 Текст:", reply_markup=back_button("admin_back"))
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    sent = 0
    for uid in users:
        try:
            await message.bot.send_message(int(uid), message.text)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    
    await message.answer(f"📢 {sent}/{len(users)}")
    await state.clear()

@admin_router.callback_query(F.data == "admin_tickets")
async def admin_tickets(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    open_tickets = [t for t in tickets if t['status'] == 'open']
    
    if not open_tickets:
        await callback.message.edit_text("📨 Нет тикетов.", reply_markup=back_button("admin_back"))
        await callback.answer()
        return
    
    text = "🎫 Тикеты:\n\n"
    builder = InlineKeyboardBuilder()
    
    for t in open_tickets[:10]:
        text += f"#{t['id']} | User {t['user_id']}\n{t['message'][:80]}...\n\n"
        builder.button(text=f"Ответ #{t['id']}", callback_data=f"ticket_{t['id']}")
    
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@admin_router.callback_query(F.data.startswith("ticket_"))
async def ticket_response(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    ticket_id = int(callback.data.replace("ticket_", ""))
    await state.update_data(ticket_id=ticket_id)
    await callback.message.edit_text(f"💬 Ответ на #{ticket_id}:", reply_markup=back_button("admin_tickets"))
    await state.set_state(AdminStates.waiting_for_ticket_response)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_ticket_response)
async def process_ticket_response(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    ticket_id = data['ticket_id']
    
    for t in tickets:
        if t['id'] == ticket_id:
            t['status'] = 'closed'
            save_data()
            try:
                await message.bot.send_message(int(t['user_id']), f"📨 Ответ:\n\n{message.text}")
            except:
                pass
            break
    
    await message.answer("✅ Отправлено.")
    await state.clear()

@admin_router.callback_query(F.data == "admin_groups")
async def admin_groups(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    if not groups:
        await callback.message.edit_text("👥 Нет групп.", reply_markup=back_button("admin_back"))
        await callback.answer()
        return
    
    text = "👥 Группы:\n\n"
    for gid, g in groups.items():
        text += f"ID: {gid}\nВладелец: {g['owner_id']}\n\n"
    
    await callback.message.edit_text(text, reply_markup=back_button("admin_back"))
    await callback.answer()

@admin_router.callback_query(F.data == "admin_markup")
async def admin_markup(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(f"💲 Наценка: {MARKUP_PERCENT}%\n\nНовый процент:", reply_markup=back_button("admin_back"))
    await state.set_state(AdminStates.waiting_for_markup)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_markup)
async def process_markup(message: Message, state: FSMContext):
    global MARKUP_PERCENT
    if not is_admin(message.from_user.id):
        return
    
    try:
        MARKUP_PERCENT = int(message.text.strip())
        await message.answer(f"✅ Наценка: {MARKUP_PERCENT}%")
    except:
        await message.answer("❌ Число.")
    
    await state.clear()

@admin_router.callback_query(F.data == "admin_usd_rate")
async def admin_usd_rate(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(f"💱 Курс USDT: {USD_RATE}₽\n\nНовый курс:", reply_markup=back_button("admin_back"))
    await state.set_state(AdminStates.waiting_for_usd_rate)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_usd_rate)
async def process_usd_rate(message: Message, state: FSMContext):
    global USD_RATE
    if not is_admin(message.from_user.id):
        return
    
    try:
        USD_RATE = float(message.text.strip())
        await message.answer(f"✅ Курс: 1 USDT = {USD_RATE}₽")
    except:
        await message.answer("❌ Число.")
    
    await state.clear()

@admin_router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🔧 Админ-панель", reply_markup=get_admin_keyboard())
    await callback.answer()

@admin_router.callback_query(F.data == "admin_exit")
async def admin_exit(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

# ============================================
# bot
# ============================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(admin_router)
dp.include_router(group_router)
dp.include_router(user_router)

async def main():
    logger.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
