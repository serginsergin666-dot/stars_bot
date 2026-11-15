import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# --- НАСТРОЙКИ ---
TOKEN="9025626800:AAG13eU8f1JwQmYFG4ARzM7-YIfgP8DS6K4"  # <--- Сюда токен от BotFather
ADMIN_ID=1689452070  # <--- Сюда твой цифровой ID из @userinfobot
MY_CARD_NUMBER="4874 0700 2555 6083"  # <--- Сюда номер твоей карты Монобанка
SUPPORT_USERNAME = "@attackbrutal"  # <--- Сюда твой юзернейм для поддержки (без @)

router = Router()


# Состояния для ожидания скриншота
class PaymentState(StatesGroup):
  waiting_for_receipt = State()


# Пакеты звезд (названия и цены)
STARS_PACKAGES = {
    "50 ⭐": {"stars": 50, "price": 45},
    "100 ⭐": {"stars": 100, "price": 90},
    "250 ⭐": {"stars": 250, "price": 220},
}


# 1. Команда /start (Главное меню)
@router.message(CommandStart())
async def cmd_start(message: Message):
  # Клавиатура с выбором звезд и поддержкой
  keyboard_buttons = []
  for title in STARS_PACKAGES.keys():
    keyboard_buttons.append(
        [InlineKeyboardButton(text=f"Купить {title}", callback_data=f"buy_{title}")]
    )

  # Добавляем кнопку связи с поддержкой
  keyboard_buttons.append([
      InlineKeyboardButton(
          text="💬 Поддержка / FAQ", url=f"https://t.me/{SUPPORT_USERNAME}"
      )
  ])

  markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

  text = (
      "⭐ <b>Добро пожаловать в официальный сервис Telegram Stars UA!</b>\n\n"
      "Здесь вы можете приобрести звезды за украинские гривны (UAH).\n"
      "Выберите нужное количество звезд ниже:"
  )

  await message.answer(text, reply_markup=markup, parse_mode="HTML")


# 2. Обработка нажатия на пакет звезд
@router.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: CallbackQuery, state: FSMContext):
  package_key = callback.data.split("_", 1)[1]
  package_info = STARS_PACKAGES.get(package_key)

  if not package_info:
    return await callback.answer("Пакет не найден!", show_alert=True)

  stars_count = package_info["stars"]
  price = package_info["price"]

  # Сохраняем в память сколько звезд покупает юзер
  await state.update_data(stars=stars_count)

  text = (
      f"⭐ Покупка: <b>{stars_count} Звезд</b>\n"
      f"💰 Сумма к оплате: <b>{price} UAH</b>\n\n"
      f"💳 Переведите точную сумму на карту Монобанка:\n"
      f"<code>{MY_CARD_NUMBER}</code>\n\n"
      f"⚠️ После оплаты <b>отправьте скриншот чека (фото)</b> в этот чат."
  )

  await callback.message.answer(text, parse_mode="HTML")
  await state.set_state(PaymentState.waiting_for_receipt)
  await callback.answer()


# 3. Прием скриншота от пользователя
@router.message(PaymentState.waiting_for_receipt, F.photo)
async def receive_receipt(message: Message, state: FSMContext):
  user_data = await state.get_data()
  stars_count = user_data.get("stars", 0)

  photo_id = message.photo[-1].file_id
  user_id = message.from_user.id
  username = (
      f"@{message.from_user.username}"
      if message.from_user.username
      else "без юзернейма"
  )

  # Кнопки админа
  admin_markup = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="✅ Подтвердить",
                  callback_data=f"confirm_{user_id}_{stars_count}",
              ),
              InlineKeyboardButton(
                  text="❌ Отклонить", callback_data=f"decline_{user_id}"
              ),
          ]
      ]
  )

  # Пересылаем чек тебе в ЛС
  await message.bot.send_photo(
      chat_id=ADMIN_ID,
      photo=photo_id,
      caption=(
          f"🔔 <b>Новый чек на оплату!</b>\n\n"
          f"От: {username} (ID: <code>{user_id}</code>)\n"
          f"Покупка: <b>{stars_count} звезд</b>"
      ),
      reply_markup=admin_markup,
      parse_mode="HTML",
  )

  await message.answer(
      "✅ Чек принят! Ожидайте проверки администратором. Обычно это занимает"
      " пару минут."
  )
  await state.clear()


# 4. Админ нажал "Подтвердить"
@router.callback_query(F.data.startswith("confirm_"))
async def admin_confirm(callback: CallbackQuery):
  if callback.from_user.id != ADMIN_ID:
    return await callback.answer("Ты не админ!", show_alert=True)

  parts = callback.data.split("_")
  target_user_id = parts[1]
  stars_count = parts[2]

  # Пишем клиенту об успехе
  await callback.bot.send_message(
      chat_id=target_user_id,
      text=(
          f"🎉 Оплата подтверждена! Вам зачислено <b>{stars_count} Звезд</b>."
          " Спасибо за покупку!"
      ),
      parse_mode="HTML",
  )

  await callback.message.edit_caption(
      caption=callback.message.caption + "\n\n<b>✅ СТАТУС: Одобрено</b>",
      parse_mode="HTML",
  )
  await callback.answer("Заказ подтвержден!")


# 5. Админ нажал "Отклонить"
@router.callback_query(F.data.startswith("decline_"))
async def admin_decline(callback: CallbackQuery):
  if callback.from_user.id != ADMIN_ID:
    return await callback.answer("Ты не админ!", show_alert=True)

  target_user_id = callback.data.split("_")[1]

  await callback.bot.send_message(
      chat_id=target_user_id,
      text=(
          "❌ Ваша оплата была отклонена. Если это ошибка, напишите в"
          f" поддержку: @{SUPPORT_USERNAME}"
      ),
  )

  await callback.message.edit_caption(
      caption=callback.message.caption + "\n\n<b>❌ СТАТУС: Отклонено</b>",
      parse_mode="HTML",
  )
  await callback.answer("Заказ отклонен.")


# --- ЗАПУСК БОТА ---
async def main():
  bot = Bot(token=TOKEN)
  dp = Dispatcher()
  dp.include_router(router)

  print("Бот запущен и готов к работе!")
  await dp.start_polling(bot)


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO)
  asyncio.run(main())
