# ============================================
# bot.py - IMO Shop (smsfast + CryptoBot) — PREMIUM DESIGN
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
                if 'ACCESS_BALANCE:' in text:
                    return text.split(':')[1]
                return '0'
    
    async def get_price(self, country: str) -> float:
        async with aiohttp.ClientSession() as session:
            params = {'api_key': self.api_key, 'action': 'getPrices', 'service': 'im', 'country': country}
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                if 'BAD' in text:
                    return 0
                try:
                    data = json.loads(text)
                    for services in data.values():
                        if 'im' in services:
                            return float(services['im']['cost'])
                except:
                    pass
        return 0
    
    async def buy_number(self, country: str) -> Dict:
        async with aiohttp.ClientSession() as session:
            params = {'api_key': self.api_key, 'action': 'getNumber', 'service': 'im', 'country': country}
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                if 'ACCESS_NUMBER:' in text:
                    parts = text.split(':')
                    return {'id': parts[1], 'phone': parts[2]}
                return {'error': text}
    
    async def get_sms(self, activation_id: str) -> str:
        async with aiohttp.ClientSession() as session:
            params = {'api_key': self.api_key, 'action': 'getStatus', 'id': activation_id}
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                if 'STATUS_OK:' in text:
                    return text.split(':')[1].strip()
                elif 'STATUS_WAIT_RETRY:' in text:
                    return text.split(':')[1].strip()
        return ''
    
    async def set_status(self, activation_id: str, status: str):
        async with aiohttp.ClientSession() as session:
            params = {'api_key': self.api_key, 'action': 'setStatus', 'status': status, 'id': activation_id}
            async with session.get(self.base_url, params=params) as resp:
                return await resp.text()

class CryptoService:
    def __init__(self):
        self.api_key = CRYPTOBOT_API_KEY
        self.base_url = 'https://pay.crypt.bot/api'
    
    async def create_invoice(self, amount_usdt: float, user_id: int) -> Dict:
        async with aiohttp.ClientSession() as session:
            headers = {'Content-Type': 'application/json', 'Crypto-Pay-API-Token': self.api_key}
            data = {
                'asset': 'USDT', 'amount': str(amount_usdt),
                'description': 'Пополнение баланса IMO Shop',
                'payload': str(user_id), 'allow_anonymous': False,
                'paid_btn_name': 'callback', 'paid_btn_url': 'https://t.me/imo_shop_bot'
            }
            async with session.post(f'{self.base_url}/createInvoice', headers=headers, json=data) as resp:
                result = await resp.json()
                if result.get('ok'):
                    return result.get('result', {})
                return result
    
    async def get_invoice(self, invoice_id: int) -> Dict:
        async with aiohttp.ClientSession() as session:
            headers = {'Content-Type': 'application/json', 'Crypto-Pay-API-Token': self.api_key}
            data = {'invoice_ids': str(invoice_id)}
            async with session.post(f'{self.base_url}/getInvoices', headers=headers, json=data) as resp:
                result = await resp.json()
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
    builder.button(text="👤 Профиль", callback_data="my_profile")
    builder.button(text="💎 Пополнить баланс", callback_data="top_up")
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
    builder.button(text="💵 Начислить баланс", callback_data="admin_add_balance")
    builder.button(text="💸 Списать баланс", callback_data="admin_remove_balance")
    builder.button(text="🚫 Бан / Разбан", callback_data="admin_ban")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="🎫 Тикеты", callback_data="admin_tickets")
    builder.button(text="👥 Группы", callback_data="admin_groups")
    builder.button(text="💲 Наценка", callback_data="admin_markup")
    builder.button(text="💱 Курс USDT", callback_data="admin_usd_rate")
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
    builder.button(text="🌟 Самый дешёвый (США вирт)", callback_data="country_12")
    for code, name in COUNTRIES.items():
        if code != '12':
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
    await message.answer(
        "✨ <b>Добро пожаловать в IMO Shop!</b>\n\n"
        "🌟 Покупайте аккаунты IMO по выгодным ценам\n"
        "🌍 Все страны доступны\n"
        "⚡ Мгновенная выдача номера\n"
        "💎 Пополнение через CryptoBot (USDT)\n\n"
        "<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

@user_router.callback_query(F.data == "buy_imo")
async def buy_imo(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛒 <b>Покупка IMO аккаунта</b>\n\n"
        "<i>Выберите страну:</i>",
        parse_mode="HTML",
        reply_markup=get_countries_keyboard()
    )
    await callback.answer()

@user_router.callback_query(F.data.startswith("country_"))
async def select_country(callback: CallbackQuery):
    country = callback.data.replace("country_", "")
    await callback.message.edit_text("🔍 <i>Получаю актуальную цену...</i>", parse_mode="HTML")
    
    api_price = await smsfast_service.get_price(country)
    
    if api_price <= 0:
        await callback.message.edit_text(
            "❌ <b>Нет доступных номеров</b>\n\n<i>Попробуйте другую страну</i>",
            parse_mode="HTML",
            reply_markup=back_button("buy_imo")
        )
        await callback.answer()
        return
    
    price_rub = round(api_price * get_markup(), 2)
    name = COUNTRIES.get(country, f"Страна {country}")
    
    await callback.message.edit_text(
        f"🛒 <b>{name}</b>\n\n"
        f"💰 Цена: <b>{price_rub}₽</b> / шт\n"
        f"📊 Наценка: {MARKUP_PERCENT}%\n\n"
        f"<i>Выберите количество:</i>",
        parse_mode="HTML",
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
    
    if user['balance'] < total_price:
        await callback.message.edit_text(
            f"❌ <b>Недостаточно средств!</b>\n\n"
            f"🧾 {qty} шт × {price_per_one}₽ = <b>{total_price}₽</b>\n"
            f"💰 Баланс: <b>{user['balance']:.2f}₽</b>\n\n"
            f"<i>Пополните баланс в разделе «💎 Пополнить баланс»</i>",
            parse_mode="HTML",
            reply_markup=back_button("buy_imo")
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(f"🔄 <b>Покупаю {qty} шт...</b>", parse_mode="HTML")
    
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
    
    text = (
        f"✅ <b>Покупка успешна!</b>\n\n"
        f"📦 Куплено: <b>{len(success)}/{qty}</b>\n"
        f"💵 Цена: <b>{price_per_one}₽</b> / шт\n"
        f"💰 Баланс: <b>{user['balance']:.2f}₽</b>\n\n"
        f"📱 <b>Номера:</b>\n"
    )
    for s in success:
        text += f"<code>{s['phone']}</code>\n"
    text += "\n<i>Управление в разделе «📱 Мои аккаунты»</i>"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Мои аккаунты", callback_data="my_accounts")
    builder.button(text="🛒 Купить ещё", callback_data="buy_imo")
    builder.button(text="🏠 В меню", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@user_router.callback_query(F.data == "my_accounts")
async def my_accounts(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    my_list = [p for p in purchases if p['user_id'] == uid and p.get('status') != 'cancelled']
    
    if not my_list:
        await callback.message.edit_text(
            "📱 <b>Мои аккаунты</b>\n\n"
            "😕 <i>У вас пока нет активных аккаунтов</i>\n\n"
            "🛒 <i>Купите первый аккаунт в разделе «Купить IMO»</i>",
            parse_mode="HTML",
            reply_markup=back_button("main_menu")
        )
        await callback.answer()
        return
    
    text = "📱 <b>Мои аккаунты</b>\n\n"
    builder = InlineKeyboardBuilder()
    
    for p in reversed(my_list):
        status_icon = "✅" if p.get('sms_code') else "⏳"
        text += f"{status_icon} <b>{p.get('country','')}</b>\n"
        text += f"   📞 <code>{p['phone']}</code>\n"
        if p.get('sms_code'):
            text += f"   🔑 Код: <code>{p['sms_code']}</code>\n"
        text += f"   💰 {p['price_rub']}₽\n\n"
        
        builder.button(text=f"📱 {p['phone']} — {p.get('country','')}", callback_data=f"acc_{p['order_id']}")
    
    builder.button(text="🗑 Удалить все", callback_data="acc_delall")
    builder.button(text="🛒 Купить ещё", callback_data="buy_imo")
    builder.button(text="🏠 В меню", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@user_router.callback_query(F.data.startswith("acc_"))
async def acc_detail(callback: CallbackQuery):
    order_id = callback.data.replace("acc_", "")
    
    p = None
    for pur in purchases:
        if pur.get('order_id') == order_id:
            p = pur
            break
    
    if not p:
        await callback.answer("Аккаунт не найден")
        return
    
    status_text = "✅ Получен" if p.get('sms_code') else "⏳ Ожидает"
    
    text = (
        f"📱 <b>Аккаунт IMO</b>\n\n"
        f"🌍 Страна: <b>{p.get('country','')}</b>\n"
        f"📞 Номер: <code>{p['phone']}</code>\n"
        f"💰 Цена: <b>{p['price_rub']}₽</b>\n"
        f"📊 Статус: {status_text}\n"
    )
    if p.get('sms_code'):
        text += f"🔑 Код: <code>{p['sms_code']}</code>\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Получить код", callback_data=f"sms_{order_id}")
    builder.button(text="🔄 Повтор SMS", callback_data=f"resend_{order_id}")
    builder.button(text="🗑 Удалить", callback_data=f"accdel_{order_id}")
    builder.button(text="🔙 К списку", callback_data="my_accounts")
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@user_router.callback_query(F.data.startswith("accdel_"))
async def acc_delete(callback: CallbackQuery):
    order_id = callback.data.replace("accdel_", "")
    
    for p in purchases:
        if p.get('order_id') == order_id:
            p['status'] = 'cancelled'
            save_data()
            break
    
    await callback.answer("🗑 Аккаунт удалён")
    await my_accounts(callback)

@user_router.callback_query(F.data == "acc_delall")
async def acc_delete_all(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    for p in purchases:
        if p['user_id'] == uid and p.get('status') != 'cancelled':
            p['status'] = 'cancelled'
    save_data()
    
    await callback.answer("🗑 Все аккаунты удалены")
    await callback.message.edit_text(
        "📱 <b>Мои аккаунты</b>\n\n"
        "🗑 <i>Все аккаунты удалены</i>",
        parse_mode="HTML",
        reply_markup=back_button("main_menu")
    )

@user_router.callback_query(F.data.startswith("sms_"))
async def get_sms_code(callback: CallbackQuery):
    order_id = callback.data.replace("sms_", "")
    
    await callback.message.edit_text(
        "⏳ <b>Получаю код...</b>\n\n"
        "<i>Пожалуйста подождите...</i>",
        parse_mode="HTML"
    )
    
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
                f"✅ <b>Код получен!</b>\n\n"
                f"🔑 Код подтверждения:\n<code>{code}</code>\n\n"
                f"<i>Введите этот код в приложении IMO</i>",
                parse_mode="HTML",
                reply_markup=back_button(f"acc_{order_id}")
            )
            await callback.answer()
            return
    
    await callback.message.edit_text(
        "❌ <b>Код не получен</b>\n\n"
        "<i>Попробуйте нажать «Повтор SMS»</i>",
        parse_mode="HTML",
        reply_markup=back_button(f"acc_{order_id}")
    )
    await callback.answer()

@user_router.callback_query(F.data.startswith("resend_"))
async def resend_sms(callback: CallbackQuery):
    order_id = callback.data.replace("resend_", "")
    
    await smsfast_service.set_status(order_id, '3')
    
    await callback.message.edit_text("🔄 <b>Повторная отправка...</b>", parse_mode="HTML")
    
    for _ in range(30):
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
                f"✅ <b>Код получен!</b>\n\n🔑 <code>{code}</code>",
                parse_mode="HTML",
                reply_markup=back_button(f"acc_{order_id}")
            )
            await callback.answer()
            return
    
    await callback.message.edit_text("❌ Код не получен.", reply_markup=back_button(f"acc_{order_id}"))
    await callback.answer()

@user_router.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    user = get_user(uid)
    
    active = len([p for p in purchases if p['user_id'] == uid and p.get('status') != 'cancelled'])
    total_purchases = len([p for p in purchases if p['user_id'] == uid])
    
    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"💎 Баланс: <b>{user['balance']:.2f}₽</b>\n"
        f"💸 Потрачено: <b>{user['total_spent']:.2f}₽</b>\n"
        f"📱 Активных: <b>{active}</b>\n"
        f"📦 Всего покупок: <b>{total_purchases}</b>\n"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Пополнить", callback_data="top_up")
    builder.button(text="📱 Мои аккаунты", callback_data="my_accounts")
    builder.button(text="📋 История покупок", callback_data="my_purchases")
    builder.button(text="🏠 В меню", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@user_router.callback_query(F.data == "my_purchases")
async def my_purchases(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    my_list = [p for p in purchases if p['user_id'] == uid][-20:]
    
    if not my_list:
        text = "📋 <b>История покупок</b>\n\n<i>Пока пусто</i>"
    else:
        text = "📋 <b>История покупок</b>\n\n"
        for p in reversed(my_list):
            code = p.get('sms_code', 'ожидает')
            text += (
                f"🌍 {p.get('country','')}\n"
                f"📞 <code>{p['phone']}</code>\n"
                f"🔑 {code} | 💰 {p['price_rub']}₽\n"
                f"📅 {p['created_at'][:19]}\n\n"
            )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_button("my_profile"))
    await callback.answer()

@user_router.callback_query(F.data == "top_up")
async def top_up(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    for amount_usdt in [1, 2, 5, 10, 20, 50]:
        rub = round(amount_usdt * USD_RATE)
        builder.button(text=f"💎 {amount_usdt} USDT (~{rub}₽)", callback_data=f"amount_{amount_usdt}")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2)
    
    await callback.message.edit_text(
        f"💎 <b>Пополнение баланса</b>\n\n"
        f"💰 Баланс в рублях\n"
        f"💱 Курс: 1 USDT ≈ <b>{USD_RATE}₽</b>\n\n"
        f"<i>Выберите сумму пополнения:</i>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@user_router.callback_query(F.data.startswith("amount_"))
async def create_invoice(callback: CallbackQuery):
    amount_usdt = float(callback.data.replace("amount_", ""))
    
    try:
        invoice = await crypto_service.create_invoice(amount_usdt, callback.from_user.id)
        
        if 'pay_url' not in invoice:
            await callback.message.edit_text(
                "❌ <b>Ошибка создания счёта</b>\n\n<i>Попробуйте позже</i>",
                parse_mode="HTML",
                reply_markup=back_button("top_up")
            )
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        builder.button(text="💎 Оплатить", url=invoice['pay_url'])
        builder.button(text="🔄 Проверить оплату", callback_data=f"check_{invoice['invoice_id']}")
        builder.button(text="🔙 Назад", callback_data="top_up")
        builder.adjust(1)
        
        await callback.message.edit_text(
            f"💳 <b>Счёт на оплату</b>\n\n"
            f"№ <code>{invoice['invoice_id']}</code>\n"
            f"💎 Сумма: <b>{amount_usdt} USDT</b>\n"
            f"💰 Зачисление: ~<b>{round(amount_usdt * USD_RATE)}₽</b>\n\n"
            f"👇 <i>Нажмите кнопку для оплаты</i>\n"
            f"⏱ Счёт действителен 30 минут",
            parse_mode="HTML",
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
                'user_id': uid, 'type': 'deposit', 'amount': amount_rub,
                'description': f'Пополнение #{invoice_id} ({amount_usdt} USDT)',
                'invoice_id': invoice_id, 'created_at': str(datetime.now())
            })
            save_data()
            
            await callback.message.edit_text(
                f"✅ <b>Оплата прошла успешно!</b>\n\n"
                f"💎 Сумма: <b>{amount_usdt} USDT</b>\n"
                f"💰 Зачислено: <b>+{amount_rub}₽</b>\n"
                f"💳 Баланс: <b>{user['balance']:.2f}₽</b>",
                parse_mode="HTML",
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
    await callback.message.edit_text(
        "💬 <b>Поддержка</b>\n\n"
        "<i>Опишите вашу проблему и мы ответим в ближайшее время.</i>",
        parse_mode="HTML",
        reply_markup=back_button("main_menu")
    )
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
    await message.answer(
        f"✅ <b>Обращение #{tickets[-1]['id']} принято</b>\n\n"
        "<i>Мы ответим вам в ближайшее время.</i>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    await state.clear()

@user_router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "✨ <b>IMO Shop</b>\n\n"
        "<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
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
    
    await message.answer(
        f"✅ <b>Группа подключена!</b>\n\n"
        f"👥 Участники могут покупать: /buy\n"
        f"💳 Списание с вашего баланса\n"
        f"💰 Ваш баланс: <b>{user['balance']:.2f}₽</b>",
        parse_mode="HTML"
    )

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
        await message.answer("❌ Покупки недоступны. У владельца недостаточно средств.")
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🌟 США вирт (дешёвый)", callback_data=f"g_12_{message.chat.id}")
    for code in list(COUNTRIES.keys())[:6]:
        if code != '12':
            builder.button(text=COUNTRIES[code], callback_data=f"g_{code}_{message.chat.id}")
    builder.adjust(2)
    
    await message.answer("🛒 <b>Выберите страну:</b>", parse_mode="HTML", reply_markup=builder.as_markup())

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
    
    await callback.message.edit_text("🔄 <b>Покупаю...</b>", parse_mode="HTML")
    
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
        
        text = (
            f"✅ <b>Аккаунт куплен!</b>\n\n"
            f"📞 Номер: <code>{phone}</code>\n"
            f"🌍 {COUNTRIES.get(country, country)}\n"
            f"💰 Списано: <b>{price_rub}₽</b>\n\n"
            f"<i>Введите номер в IMO и получите код:</i>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📩 Получить код", callback_data=f"sms_{order_id}")
        builder.button(text="🔄 Повтор SMS", callback_data=f"resend_{order_id}")
        builder.adjust(1)
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        await callback.answer()
    else:
        await callback.message.edit_text("❌ Ошибка покупки.")
        await callback.answer()

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
    await message.answer(
        "🔧 <b>Админ-панель</b>\n\n<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

@admin_router.callback_query(F.data == "admin_balance")
async def admin_balance(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    try:
        bal = await smsfast_service.get_balance()
        price = await smsfast_service.get_price('12')
        price_rub = round(price * get_markup(), 2) if price else 0
        text = (
            f"💰 <b>Баланс smsfas.vip</b>\n\n"
            f"🟢 <b>{bal}₽</b>\n\n"
            f"📱 IMO (США вирт): <b>{price_rub}₽</b>\n"
            f"💱 Курс: 1 USDT = <b>{USD_RATE}₽</b>"
        )
    except:
        text = "💰 Баланс\n\n❌ Ошибка"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="admin_balance")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@admin_router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    text = f"👥 <b>Пользователи ({len(users)})</b>\n\n"
    for uid, u in list(users.items())[:20]:
        status = "🟢" if not u.get('is_banned') else "🚫"
        text += f"{status} <code>{uid}</code> | @{u.get('username','нет')} | {u['balance']:.2f}₽\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_button("admin_back"))
    await callback.answer()

@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    today = str(datetime.now().date())
    today_purchases = [p for p in purchases if p['created_at'][:10] == today]
    
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{len(users)}</b>\n"
        f"👥 Групп: <b>{len(groups)}</b>\n\n"
        f"🛒 Сегодня: <b>{len(today_purchases)} шт</b> / {sum(p['price_rub'] for p in today_purchases):.2f}₽\n"
        f"🛒 Всего: <b>{len(purchases)} шт</b> / {sum(p['price_rub'] for p in purchases):.2f}₽\n\n"
        f"💲 Наценка: <b>{MARKUP_PERCENT}%</b>\n"
        f"💱 Курс USDT: <b>{USD_RATE}₽</b>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="admin_stats")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@admin_router.callback_query(F.data == "admin_add_balance")
async def admin_add_balance(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "💵 <b>Начислить баланс</b>\n\n<i>Введите ID и сумму:</i>\n<code>123456789 1000</code>",
        parse_mode="HTML",
        reply_markup=back_button("admin_back")
    )
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
        transactions.append({'user_id': uid, 'type': 'deposit', 'amount': amount, 'description': 'Админ', 'created_at': str(datetime.now())})
        save_data()
        
        await message.answer(f"✅ +{amount}₽ пользователю {user_id}\nБаланс: {user['balance']:.2f}₽")
        try:
            await message.bot.send_message(int(user_id), f"💰 Баланс пополнен на {amount}₽\nТекущий: {user['balance']:.2f}₽")
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
        
        if uid in users and users[uid]['balance'] >= amount:
            users[uid]['balance'] -= amount
            save_data()
            await message.answer(f"✅ -{amount}₽ у {user_id}\nОстаток: {users[uid]['balance']:.2f}₽")
        else:
            await message.answer("❌ Недостаточно средств или пользователь не найден.")
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
    await callback.message.edit_text("📢 Текст рассылки:", reply_markup=back_button("admin_back"))
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
    
    await message.answer(f"📢 Отправлено: {sent}/{len(users)}")
    await state.clear()

@admin_router.callback_query(F.data == "admin_tickets")
async def admin_tickets(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    open_tickets = [t for t in tickets if t['status'] == 'open']
    
    if not open_tickets:
        await callback.message.edit_text("📨 Нет открытых тикетов.", reply_markup=back_button("admin_back"))
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
    await callback.message.edit_text("🔧 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
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
