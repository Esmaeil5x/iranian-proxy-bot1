import os
import asyncio
import aiohttp
import re
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import logging

# تنظیم لاگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

class IranianProxyBot:
    def __init__(self):
        self.proxy_sources = [
            "https://www.proxy-list.download/api/v1/get?type=http&country=IR",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt"
        ]
        
        # IP ranges ایران (خلاصه شده)
        self.iran_ip_ranges = [
            "2.176.0.0/12", "37.156.0.0/14", "78.157.0.0/16", 
            "91.98.0.0/15", "178.22.0.0/15", "185.55.224.0/22"
        ]

    async def is_iranian_ip(self, ip):
        """چک کردن IP ایرانی"""
        import ipaddress
        try:
            ip_obj = ipaddress.ip_address(ip)
            for range_str in self.iran_ip_ranges:
                if ip_obj in ipaddress.ip_network(range_str):
                    return True
        except:
            pass
        return False

    async def fetch_proxies_from_url(self, url):
        """دریافت پروکسی از URL"""
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
        """استخراج پروکسی از متن"""
        proxy_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})'
        matches = re.findall(proxy_pattern, content)
        return [f"{ip}:{port}" for ip, port in matches]

    async def test_proxy(self, proxy, timeout=8):
        """تست پروکسی"""
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
        """اصلی - دریافت پروکسی ایرانی"""
        chat_id = update.effective_chat.id
        
        status_message = await context.bot.send_message(
            chat_id, "🔍 در حال جستجو... لطفاً صبر کنید"
        )
        
        all_proxies = []
        
        # جمع‌آوری از منابع
        for i, url in enumerate(self.proxy_sources):
            await context.bot.edit_message_text(
                f"🔍 منبع {i+1}/{len(self.proxy_sources)}...",
                chat_id=chat_id, message_id=status_message.message_id
            )
            proxies = await self.fetch_proxies_from_url(url)
            all_proxies.extend(proxies)
        
        unique_proxies = list(set(all_proxies))
        
        # فیلتر ایرانی
        iranian_proxies = []
        for proxy in unique_proxies:
            ip = proxy.split(':')[0]
            if await self.is_iranian_ip(ip):
                iranian_proxies.append(proxy)
        
        await context.bot.edit_message_text(
            f"🇮🇷 {len(iranian_proxies)} پروکسی ایرانی - در حال تست...",
            chat_id=chat_id, message_id=status_message.message_id
        )
        
        # تست پروکسی‌ها
        working_proxies = []
        for i, proxy in enumerate(iranian_proxies[:20]):  # فقط 20 تا برای سرعت
            is_working, response_time = await self.test_proxy(proxy)
            if is_working:
                working_proxies.append({'proxy': proxy, 'response_time': response_time})
        
        working_proxies.sort(key=lambda x: x['response_time'])
        
        await context.bot.delete_message(chat_id, status_message.message_id)
        
        # ارسال نتایج
        if working_proxies:
            message = f"✅ **پروکسی‌های ایرانی سالم** ({len(working_proxies)} عدد)\n\n"
            message += f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
            
            for proxy_info in working_proxies:
                proxy = proxy_info['proxy']
                speed = proxy_info['response_time']
                message += f"`{proxy}` - {speed}ms\n"
            
            await context.bot.send_message(chat_id, message, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id, "❌ پروکسی سالمی پیدا نشد!")

proxy_bot = IranianProxyBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇮🇷 دریافت پروکسی ایرانی", callback_data="get_proxies")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """🤖 **ربات پروکسی ایرانی**

🔍 پیدا کردن پروکسی‌های ایرانی رایگان
⚡ تست سرعت و سلامت
📋 لیست پروکسی‌های سالم

برای شروع دکمه زیر را بزنید:"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "get_proxies":
        await proxy_bot.get_iranian_proxies(update, context)
    elif query.data == "help":
        help_text = """📖 **راهنما:**

🔹 /start - شروع ربات
🔹 /proxy - دریافت پروکسی

**نکات:**
⚠️ پروکسی‌ها موقتی هستند
⚠️ سرعت متغیر است
⚠️ برای امنیت از HTTPS استفاده کنید"""
        await query.edit_message_text(help_text, parse_mode='Markdown')

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN تنظیم نشده!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("proxy", lambda u, c: proxy_bot.get_iranian_proxies(u, c)))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 ربات شروع شد...")
    application.run_polling()

if __name__ == '__main__':
    main()