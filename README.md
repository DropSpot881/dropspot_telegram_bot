# Sørlandets Shop Bot 🤖

A Telegram autoshop bot with dead drop pickups, home delivery, and crypto/cash payments.

## Features

- 🛒 **Product catalog** with categories
- 🛍️ **Cart system** with add/remove/clear
- 📍 **Dead Drop** — secret pickup locations assigned after order confirmation
- 📦 **Home Delivery (Post)** — shipped via mail
- 🚀 **Home Delivery (Today)** — same-day delivery
- ₿ **Crypto payments** — BTC / ETH wallet display
- 💵 **Cash payments** — pay on delivery/pickup
- 🔧 **Admin panel** — manage everything via `/admin`

## Setup

### 1. Create a Telegram Bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Get Your Telegram User ID
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. Copy your user ID number

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
copy .env.example .env
```

Edit `.env` with your values:
```
BOT_TOKEN=your-bot-token
ADMIN_IDS=your-user-id
CRYPTO_WALLET_BTC=your-btc-address
CRYPTO_WALLET_ETH=your-eth-address
```

### 5. Run the Bot

```bash
python -m bot.main
```

## Usage

### Customer Commands
- `/start` — Open main menu (Shop, Cart, Orders, Help)

### Admin Commands
- `/admin` — Open admin panel
  - **Categories**: Add / delete categories
  - **Products**: Add / delete / toggle stock
  - **Locations**: Add / delete / toggle dead drop locations
  - **Orders**: View, confirm, ship, complete, or cancel orders

## Order Flow

1. Customer browses shop → adds to cart
2. Customer checks out → chooses delivery & payment
3. Customer follows payment instructions
4. Customer clicks "I Have Paid"
5. Admin gets notification → confirms order
6. **Dead Drop**: Customer receives secret pickup location
7. **Home Delivery**: Customer gets shipping updates
