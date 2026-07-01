# ============================================
# bot.py - IMO Shop (smsfast + CryptoBot)
# ============================================

import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
from typing import Dict

import aiohttp
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, select, func
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# ============================================
# НАСТРОЙКИ
# ============================================
BOT_TOKEN = '8724614250:AAGK3KkM1qJWQIu0UqvvhPpEbxViBMHglFI'
ADMIN_IDS = [8632861931,743956377]  # твой ID
SMSFAST_API_KEY = 'Lwx5xNXcAATYznbQmrm6DnkIlwFhAz'
CRYPTOBOT_API_KEY = '590558:AATFDxdtESm34k9IoB2U7TLAo0LQylVdmPo'
MARKUP_PERCENT = 20
USD_RATE = 75

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
# database
# ============================================
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String)
    balance = Column(Float, default=0)
    total_spent = Column(Float, default=0)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now)

class Purchase(Base):
    __tablename__ = 'purchases'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    country = Column(String)
    phone = Column(String)
    sms_code = Column(String)
    price_rub = Column(Float)
    group_id = Column(Integer, nullable=True)
    group_owner_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, unique=True)
    owner_id = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    type = Column(String)
    amount = Column(Float)
    description = Column(String)
    invoice_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class SupportTicket(Base):
    __tablename__ = 'support_tickets'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    message = Column(String)
    status = Column(String, default='open')
    created_at = Column(DateTime, default=datetime.now)

engine = create_async_engine('sqlite+aiosqlite:///bot.db')
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

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
                    for c, services in data.items():
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
                    return text.split(':')[1]
                return ''
    
    async def cancel_order(self, activation_id: str):
        async with aiohttp.ClientSession() as session:
            params = {'api_key': self.api_key, 'action': 'setStatus', 'status': '8', 'id': activation_id}
            async with session.get(self.base_url, params=params) as resp:
                return await resp.text()

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
                logger.info(f"CryptoBot создание: {result}")
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
                logger.info(f"CryptoBot проверка: {result}")
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
async def cmd_start(message: Message, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    if not user:
        user = User(telegram_id=message.from_user.id, username=message.from_user.username)
        session.add(user)
        try:
            await session.commit()
        except:
            await session.rollback()
    else:
        user.username = message.from_user.username
        await session.commit()
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
async def process_quantity(callback: CallbackQuery, session: AsyncSession):
    _, qty, price_per_one, country = callback.data.split("_")
    qty = int(qty)
    price_per_one = float(price_per_one)
    total_price = round(price_per_one * qty, 2)
    
    user = await session.get(User, callback.from_user.id)
    
    if not user:
        await callback.message.edit_text("❌ Нажмите /start", reply_markup=back_button("main_menu"))
        await callback.answer()
        return
    
    if user.balance < total_price:
        await callback.message.edit_text(
            f"❌ Недостаточно средств!\n{qty} шт × {price_per_one}₽ = {total_price}₽\nБаланс: {user.balance:.2f}₽",
            reply_markup=back_button("buy_imo")
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(f"🔄 Покупаю {qty} шт...\n0/{qty}")
    
    success = []
    failed = 0
    
    for i in range(qty):
        result = await smsfast_service.buy_number(country)
        
        if result.get('id') and 'error' not in result:
            order_id = result['id']
            phone = result['phone']
            
            for _ in range(30):
                await asyncio.sleep(2)
                code = await smsfast_service.get_sms(order_id)
                if code:
                    user.balance -= price_per_one
                    user.total_spent += price_per_one
                    user.last_activity = datetime.now()
                    
                    session.add(Purchase(user_id=user.telegram_id, country=COUNTRIES.get(country, country), phone=phone, sms_code=code, price_rub=price_per_one))
                    session.add(Transaction(user_id=user.telegram_id, type='purchase', amount=-price_per_one, description='IMO'))
                    await session.commit()
                    
                    success.append(f"📱 {phone} | 💬 {code}")
                    break
            else:
                try:
                    await smsfast_service.cancel_order(order_id)
                except:
                    pass
                failed += 1
        else:
            failed += 1
        
        await callback.message.edit_text(f"🔄 Покупаю {qty} шт...\n{i+1}/{qty}\n✅ {len(success)} | ❌ {failed}")
    
    text = f"✅ Готово!\n\nКуплено: {len(success)}/{qty}\nЦена: {price_per_one}₽/шт\nПотрачено: {round(price_per_one*len(success),2)}₽\n💰 Баланс: {user.balance:.2f}₽\n\n"
    if success:
        text += "\n".join(success[:10])
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Ещё", callback_data="buy_imo")
    builder.button(text="🔙 Меню", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@user_router.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery, session: AsyncSession):
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Нажмите /start", reply_markup=back_button("main_menu"))
        await callback.answer()
        return
    
    purchases = await session.execute(select(Purchase).where(Purchase.user_id == user.telegram_id).order_by(Purchase.created_at.desc()).limit(5))
    purchases = purchases.scalars().all()
    total = await session.scalar(select(func.count(Purchase.id)).where(Purchase.user_id == user.telegram_id))
    
    text = f"👤 Профиль\n\nID: {user.telegram_id}\n💰 Баланс: {user.balance:.2f}₽\n💸 Потрачено: {user.total_spent:.2f}₽\n📱 Покупок: {total}"
    if purchases:
        text += "\n\nПоследние:\n"
        for p in purchases:
            text += f"• {p.country} | {p.phone} — {p.price_rub}₽\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Пополнить", callback_data="top_up")
    builder.button(text="📋 Все покупки", callback_data="my_purchases")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@user_router.callback_query(F.data == "my_purchases")
async def my_purchases(callback: CallbackQuery, session: AsyncSession):
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Нажмите /start", reply_markup=back_button("my_profile"))
        await callback.answer()
        return
    
    purchases = await session.execute(select(Purchase).where(Purchase.user_id == callback.from_user.id).order_by(Purchase.created_at.desc()).limit(20))
    purchases = purchases.scalars().all()
    
    text = "📋 История:\n\n" if purchases else "📋 Нет покупок."
    for p in purchases:
        text += f"{p.country} | 📱 {p.phone}\n💬 {p.sms_code} | 💰 {p.price_rub}₽\n📅 {p.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    
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
async def check_invoice(callback: CallbackQuery, session: AsyncSession):
    invoice_id = int(callback.data.replace("check_", ""))
    
    try:
        invoice = await crypto_service.get_invoice(invoice_id)
        
        if not invoice:
            await callback.answer("Счёт не найден", show_alert=True)
            return
        
        if invoice.get('status') == 'paid':
            user = await session.get(User, callback.from_user.id)
            if not user:
                await callback.answer("Пользователь не найден", show_alert=True)
                return
            
            amount_usdt = float(invoice['amount'])
            amount_rub = round(amount_usdt * USD_RATE, 2)
            user.balance += amount_rub
            user.last_activity = datetime.now()
            
            session.add(Transaction(user_id=user.telegram_id, type='deposit', amount=amount_rub, description=f'Пополнение #{invoice_id} ({amount_usdt} USDT)', invoice_id=invoice_id))
            await session.commit()
            
            await callback.message.edit_text(
                f"✅ Оплачено!\n\nСчёт #{invoice_id}\nСумма: {amount_usdt} USDT\nЗачислено: +{amount_rub}₽\n💰 Баланс: {user.balance:.2f}₽",
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
async def process_support(message: Message, state: FSMContext, session: AsyncSession):
    ticket = SupportTicket(user_id=message.from_user.id, message=message.text)
    session.add(ticket)
    await session.commit()
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, f"📨 Тикет #{ticket.id}\nОт: {message.from_user.id}\n\n{message.text}")
        except:
            pass
    await message.answer(f"✅ #{ticket.id} принято", reply_markup=get_main_keyboard())
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
async def connect_group(message: Message, session: AsyncSession):
    if message.chat.type != 'private':
        return
    
    try:
        group_id = int(message.text.split()[1])
    except:
        await message.answer("❌ /connect [ID группы]")
        return
    
    existing = await session.get(Group, group_id)
    if existing:
        await message.answer("❌ Уже подключена.")
        return
    
    group = Group(group_id=group_id, owner_id=message.from_user.id)
    session.add(group)
    await session.commit()
    
    user = await session.get(User, message.from_user.id)
    bal = user.balance if user else 0
    
    await message.answer(f"✅ Группа подключена!\n\nУчастники: /buy\nСписание с вас.\n💰 Баланс: {bal:.2f}₽")

@group_router.message(Command('buy'))
async def buy_in_group(message: Message, session: AsyncSession):
    if message.chat.type == 'private':
        return
    
    group = await session.get(Group, message.chat.id)
    if not group:
        await message.answer("❌ Группа не подключена.")
        return
    
    owner = await session.get(User, group.owner_id)
    if not owner or owner.balance <= 0:
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
async def group_purchase(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split("_")
    country = parts[1]
    group_id = int(parts[2])
    
    group = await session.get(Group, group_id)
    if not group:
        await callback.answer("Группа не подключена.")
        return
    
    owner = await session.get(User, group.owner_id)
    if not owner:
        await callback.answer("Владелец не найден.")
        return
    
    api_price = await smsfast_service.get_price(country)
    if api_price <= 0:
        await callback.answer("Нет номеров.")
        return
    
    price_rub = round(api_price * get_markup(), 2)
    
    if owner.balance < price_rub:
        await callback.answer("Недостаточно средств.")
        return
    
    result = await smsfast_service.buy_number(country)
    
    if result.get('id') and 'error' not in result:
        order_id = result['id']
        phone = result['phone']
        
        for _ in range(30):
            await asyncio.sleep(2)
            code = await smsfast_service.get_sms(order_id)
            if code:
                owner.balance -= price_rub
                owner.total_spent += price_rub
                owner.last_activity = datetime.now()
                
                session.add(Purchase(user_id=callback.from_user.id, country=COUNTRIES.get(country, country), phone=phone, sms_code=code, price_rub=price_rub, group_id=group.id, group_owner_id=owner.telegram_id))
                session.add(Transaction(user_id=owner.telegram_id, type='purchase', amount=-price_rub, description='IMO (группа)'))
                await session.commit()
                
                await callback.message.edit_text(f"✅ Куплено!\n📱 {phone}\n💬 Код: {code}\n💰 {price_rub}₽")
                await callback.answer()
                return
        
        await smsfast_service.cancel_order(order_id)
        await callback.answer("SMS не получена.")
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
async def admin_users(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        return
    
    users = await session.execute(select(User).order_by(User.created_at.desc()).limit(20))
    users = users.scalars().all()
    total = await session.scalar(select(func.count(User.id)))
    
    text = f"👥 Пользователи ({total}):\n\n"
    for u in users:
        status = "🟢" if not u.is_banned else "🚫"
        text += f"{status} {u.telegram_id} | @{u.username or 'нет'} | {u.balance:.2f}₽\n"
    
    await callback.message.edit_text(text, reply_markup=back_button("admin_back"))
    await callback.answer()

@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        return
    
    total_users = await session.scalar(select(func.count(User.id)))
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    
    today_purchases = await session.scalar(select(func.count(Purchase.id)).where(Purchase.created_at >= today))
    today_sum = await session.scalar(select(func.sum(Purchase.price_rub)).where(Purchase.created_at >= today))
    
    week_purchases = await session.scalar(select(func.count(Purchase.id)).where(Purchase.created_at >= week_ago))
    week_sum = await session.scalar(select(func.sum(Purchase.price_rub)).where(Purchase.created_at >= week_ago))
    
    total_purchases = await session.scalar(select(func.count(Purchase.id)))
    total_sum = await session.scalar(select(func.sum(Purchase.price_rub)))
    
    groups_count = await session.scalar(select(func.count(Group.id)).where(Group.is_active == True))
    
    text = (
        f"📊 Статистика\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"👥 Групп: {groups_count}\n\n"
        f"🛒 Сегодня: {today_purchases} шт / {today_sum or 0:.2f}₽\n"
        f"🛒 Неделя: {week_purchases} шт / {week_sum or 0:.2f}₽\n"
        f"🛒 Всего: {total_purchases} шт / {total_sum or 0:.2f}₽\n\n"
        f"💲 Наценка: {MARKUP_PERCENT}%\n"
        f"💱 Курс USDT: {USD_RATE}₽"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="admin_stats")
    builder.button(text="📥 Экспорт", callback_data="admin_export")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(2)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@admin_router.callback_query(F.data == "admin_export")
async def admin_export(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        return
    
    purchases = await session.execute(select(Purchase).order_by(Purchase.created_at.desc()).limit(1000))
    purchases = purchases.scalars().all()
    
    csv_data = "ID,User,Country,Phone,SMS,Price,Date\n"
    for p in purchases:
        csv_data += f"{p.id},{p.user_id},{p.country},{p.phone},{p.sms_code},{p.price_rub},{p.created_at}\n"
    
    with open("export.csv", "w") as f:
        f.write(csv_data)
    
    await callback.message.answer_document(FSInputFile("export.csv"), caption="📥 Экспорт")
    await callback.answer("Готово!")
    os.remove("export.csv")

@admin_router.callback_query(F.data == "admin_add_balance")
async def admin_add_balance(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("💵 ID и сумма в рублях:\n123456789 1000", reply_markup=back_button("admin_back"))
    await state.set_state(AdminStates.waiting_for_add_balance)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_add_balance)
async def process_add_balance(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_id, amount = message.text.split()
        user_id = int(user_id)
        amount = float(amount)
        
        user = await session.get(User, user_id)
        if user:
            user.balance += amount
            session.add(Transaction(user_id=user_id, type='deposit', amount=amount, description='Админ'))
            await session.commit()
            await message.answer(f"✅ +{amount}₽ пользователю {user_id}\nБаланс: {user.balance:.2f}₽")
            try:
                await message.bot.send_message(user_id, f"💰 +{amount}₽\nБаланс: {user.balance:.2f}₽")
            except:
                pass
        else:
            await message.answer("❌ Не найден.")
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
async def process_remove_balance(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_id, amount = message.text.split()
        user_id = int(user_id)
        amount = float(amount)
        
        user = await session.get(User, user_id)
        if user:
            if user.balance >= amount:
                user.balance -= amount
                session.add(Transaction(user_id=user_id, type='withdrawal', amount=-amount, description='Админ'))
                await session.commit()
                await message.answer(f"✅ -{amount}₽ у {user_id}\nОстаток: {user.balance:.2f}₽")
            else:
                await message.answer(f"❌ Баланс: {user.balance:.2f}₽")
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
async def process_ban(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_id = int(message.text.strip())
        user = await session.get(User, user_id)
        if user:
            user.is_banned = not user.is_banned
            await session.commit()
            status = "заблокирован" if user.is_banned else "разблокирован"
            await message.answer(f"✅ {user_id} {status}.")
        else:
            await message.answer("❌ Не найден.")
    except:
        await message.answer("❌ Неверный ID.")
    
    await state.clear()

@admin_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("📢 Текст:", reply_markup=back_button("admin_back"))
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    
    users = await session.execute(select(User).where(User.is_banned == False))
    users = users.scalars().all()
    
    sent = 0
    for user in users:
        try:
            await message.bot.send_message(user.telegram_id, message.text)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    
    await message.answer(f"📢 {sent}/{len(users)}")
    await state.clear()

@admin_router.callback_query(F.data == "admin_tickets")
async def admin_tickets(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        return
    
    tickets = await session.execute(select(SupportTicket).where(SupportTicket.status == 'open').order_by(SupportTicket.created_at.desc()).limit(10))
    tickets = tickets.scalars().all()
    
    if not tickets:
        await callback.message.edit_text("📨 Нет тикетов.", reply_markup=back_button("admin_back"))
        await callback.answer()
        return
    
    text = "🎫 Тикеты:\n\n"
    builder = InlineKeyboardBuilder()
    
    for t in tickets:
        text += f"#{t.id} | User {t.user_id}\n{t.message[:80]}...\n\n"
        builder.button(text=f"Ответ #{t.id}", callback_data=f"ticket_{t.id}")
    
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
async def process_ticket_response(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    ticket_id = data['ticket_id']
    
    ticket = await session.get(SupportTicket, ticket_id)
    if ticket:
        ticket.status = 'closed'
        await session.commit()
        
        try:
            await message.bot.send_message(ticket.user_id, f"📨 Ответ:\n\n{message.text}")
        except:
            pass
        
        await message.answer("✅ Отправлено.")
    
    await state.clear()

@admin_router.callback_query(F.data == "admin_groups")
async def admin_groups(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        return
    
    groups = await session.execute(select(Group).where(Group.is_active == True))
    groups = groups.scalars().all()
    
    if not groups:
        await callback.message.edit_text("👥 Нет групп.", reply_markup=back_button("admin_back"))
        await callback.answer()
        return
    
    text = "👥 Группы:\n\n"
    for g in groups:
        user = await session.get(User, g.owner_id)
        username = f"@{user.username}" if user and user.username else g.owner_id
        text += f"ID: {g.group_id}\nВладелец: {username}\n\n"
    
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

async def session_middleware(handler, event, data):
    async with async_session() as session:
        data['session'] = session
        return await handler(event, data)

dp.message.middleware(session_middleware)
dp.callback_query.middleware(session_middleware)

dp.include_router(admin_router)
dp.include_router(group_router)
dp.include_router(user_router)

async def main():
    # Принудительно создаём базу
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("База создана")
    
    logger.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
