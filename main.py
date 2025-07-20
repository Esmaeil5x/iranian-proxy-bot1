import asyncio
import aiohttp
import requests
import re
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import logging
import os

# تنظیم لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توکن ربات از متغیر محیطی
BOT_TOKEN = os.environ.get('BOT_TOKEN')

class IranianProxyBot:
    def __init__(self):
        self.proxy_sources = [
            "https://www.proxy-list.download/api/v1/get?type=http&country=IR",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/proxy.txt",
        ]
        
        # IP ranges ایران
        self.iran_ip_ranges = [
            "2.176.0.0/12", "5.22.0.0/16", "5.23.0.0/16", "5.56.0.0/14",
            "37.156.0.0/14", "37.191.0.0/16", "46.209.0.0/16", "62.193.0.0/16",
            "78.157.0.0/16", "79.175.0.0/16", "80.191.0.0/16", "85.15.0.0/16",
            "87.107.0.0/16", "88.135.0.0/16", "89.165.0.0/16", "91.98.0.0/15",
            "92.114.0.0/15", "93.86.0.0/15", "94.182.0.0/15", "151.232.0.0/14",
            "176.65.192.0/18", "178.22.0.0/15", "178.131.0.0/16", "178.252.0.0/14",
            "185.4.16.0/22", "185.8.172.0/22", "185.10.68.0/22", "185.55.224.0/22"
        ]

    async def is_iranian_ip(self, ip):
        """چک کردن اینکه IP ایرانی هست یا نه"""
        import ipaddress
        try:
            ip_obj = ipaddress.ip_address(ip)
            for range_str in self.iran_ip_ranges:
                if ip_obj in ipaddress.ip_network(range_str):
                    return True
        except:
            pass
        
        # اگر از IP ranges پیدا نشد، از API برای چک کردن کشور استفاده می‌کنیم
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://ip-api.com/json/{ip}?fields=country,countryCode", timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('countryCode', '').upper() == 'IR'
        except:
            pass
        return False

    async def fetch_proxies_from_url(self, url):
        """دریافت پروکسی از یک URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as response:
                    if response.status == 200:
                        content = await response.text()
                        return self.extract_proxies(content)
        except Exception as e:
            logger.error(f"خطا در دریافت از {url}: {e}")
        return []

    def extract_proxies(self, content):
        """استخراج پروکسی‌ها از متن"""
        proxy_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})'
        matches = re.findall(proxy_pattern, content)
        return [f"{ip}:{port}" for ip, port in matches]

    async def test_proxy(self, proxy, timeout=10):
        """تست یک پروکسی"""
        try:            
            async with aiohttp.ClientSession() as session:
                start_time = time.time()
                async with session.get(
                    'http://httpbin.org/ip', 
                    proxy=f'http://{proxy}',
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        end_time = time.time()
                        response_time = round((end_time - start_time) * 1000, 2)
                        return True, response_time
        except:
            pass
        return False, None

    async def get_iranian_proxies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دریافت پروکسی‌های ایرانی و تست آنها"""
        chat_id = update.effective_chat.id
        
        # ارسال پیام شروع
        status_message = await context.bot.send_message(
            chat_id, 
            "🔍 در حال جستجوی پروکسی‌های ایرانی...\nلطفاً صبر کنید..."
        )
        
        all_proxies = []
        
        # جمع‌آوری پروکسی از منابع مختلف
        for i, url in enumerate(self.proxy_sources):
            await context.bot.edit_message_text(
                f"🔍 در حال بررسی منبع {i+1}/{len(self.proxy_sources)}...",
                chat_id=chat_id,
                message_id=status_message.message_id
            )
            proxies = await self.fetch_proxies_from_url(url)
            all_proxies.extend(proxies)
        
        # حذف تکراری‌ها
        unique_proxies = list(set(all_proxies))
        
        await context.bot.edit_message_text(
            f"📊 {len(unique_proxies)} پروکسی پیدا شد\n🔍 در حال فیلتر کردن پروکسی‌های ایرانی...",
            chat_id=chat_id,
            message_id=status_message.message_id
        )
        
        # فیلتر کردن پروکسی‌های ایرانی
        iranian_proxies = []
        for proxy in unique_proxies:
            ip = proxy.split(':')[0]
            if await self.is_iranian_ip(ip):
                iranian_proxies.append(proxy)
        
        await context.bot.edit_message_text(
            f"🇮🇷 {len(iranian_proxies)} پروکسی ایرانی پیدا شد\n⚡ در حال تست کردن...",
            chat_id=chat_id,
            message_id=status_message.message_id
        )
        
        # تست پروکسی‌های ایرانی
        working_proxies = []
        total = len(iranian_proxies)
        
        for i, proxy in enumerate(iranian_proxies):
            if i % 5 == 0:  # هر 5 تا یکبار آپدیت کن
                await context.bot.edit_message_text(
                    f"⚡ تست شده: {i}/{total}\n✅ سالم: {len(working_proxies)}",
                    chat_id=chat_id,
                    message_id=status_message.message_id
                )
            
            is_working, response_time = await self.test_proxy(proxy)
            if is_working:
                working_proxies.append({
                    'proxy': proxy,
                    'response_time': response_time
                })
        
        # مرتب‌سازی بر اساس سرعت
        working_proxies.sort(key=lambda x: x['response_time'])
        
        # حذف پیام وضعیت
        await context.bot.delete_message(chat_id, status_message.message_id)
        
        # ارسال نتایج
        if working_proxies:
            message = f"✅ **پروکسی‌های ایرانی سالم** ({len(working_proxies)} عدد)\n\n"
            message += f"🕐 آخرین بروزرسانی: {datetime.now().strftime('%H:%M:%S')}\n\n"
            
            for i, proxy_info in enumerate(working_proxies[:20], 1):  # فقط 20 تای اول
                proxy = proxy_info['proxy']
                speed = proxy_info['response_time']
                message += f"`{proxy}` - {speed}ms\n"
            
            if len(working_proxies) > 20:
                message += f"\n... و {len(working_proxies) - 20} پروکسی دیگر"
            
            # ارسال در چند پیام اگر خیلی طولانی باشد
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await context.bot.send_message(chat_id, chunk, parse_mode='Markdown')
            else:
                await context.bot.send_message(chat_id, message, parse_mode='Markdown')
        else:
            await context.bot.send_message(
                chat_id, 
                "❌ متأسفانه هیچ پروکسی ایرانی سالمی پیدا نشد!\nلطفاً بعداً دوباره تلاش کنید."
            )

# تعریف handlers
proxy_bot = IranianProxyBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پیام خوشامدگویی"""
    keyboard = [
        [InlineKeyboardButton("🇮🇷 دریافت پروکسی ایرانی", callback_data="get_proxies")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """
🤖 **ربات پروکسی ایرانی** به شما خوش آمدید!

این ربات به شما کمک می‌کند تا:
🔍 پروکسی‌های ایرانی رایگان پیدا کنید
⚡ سرعت و سلامت آنها را تست کند
📋 لیست پروکسی‌های سالم را دریافت کنید

برای شروع روی دکمه زیر کلیک کنید:
    """
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت دکمه‌ها"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "get_proxies":
        await proxy_bot.get_iranian_proxies(update, context)
    elif query.data == "help":
        help_text = """
📖 **راهنمای استفاده:**

🔹 /start - شروع ربات
🔹 /proxy - دریافت پروکسی‌های ایرانی
🔹 /help - نمایش این راهنما

**نکات مهم:**
⚠️ پروکسی‌ها ممکن است بعد از مدتی غیرفعال شوند
⚠️ برای اتصال امن، از پروکسی‌های HTTPS استفاده کنید
⚠️ سرعت پروکسی‌ها متغیر است

**پشتیبانی:** @your_support_username
        """
        await query.edit_message_text(help_text, parse_mode='Markdown')

async def proxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور مستقیم دریافت پروکسی"""
    await proxy_bot.get_iranian_proxies(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنما"""
    help_text = """
📖 **راهنمای ربات پروکسی ایرانی:**

**دستورات:**
🔹 /start - شروع ربات
🔹 /proxy - دریافت پروکسی‌های ایرانی
🔹 /help - نمایش راهنما

**چگونه کار می‌کند:**
1️⃣ ربات از چندین منبع معتبر پروکسی جمع‌آوری می‌کند
2️⃣ پروکسی‌های ایرانی را فیلتر می‌کند
3️⃣ هر پروکسی را تست می‌کند
4️⃣ فقط پروکسی‌های سالم را ارسال می‌کند

**توضیح خروجی:**
• آدرس IP و پورت پروکسی
• زمان پاسخ به میلی‌ثانیه (سرعت)
• مرتب‌سازی از سریع‌ترین به کندترین

⚠️ **توجه:** پروکسی‌ها ممکن است بعد از مدتی غیرفعال شوند.
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """اجرای ربات"""
    if not BOT_TOKEN:
        print("❌ خطا: BOT_TOKEN تنظیم نشده است!")
        return
    
    # ایجاد Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # اضافه کردن handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("proxy", proxy_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # اجرای ربات
    print("🤖 ربات در حال اجرا...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()