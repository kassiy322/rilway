from asyncio import Queue
import asyncio
import pandas as pd
import re
import phonenumbers
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import validators
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import io
from aiogram.types import BufferedInputFile

BOT_TOKEN = '7156410080:AAHJbb_lMOCLNbAeRCmJkzyV22Ur9M1OaJk'
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def get_telegram_info(url, page, max_retries=3):
    for attempt in range(max_retries):
        try:
            await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())

            print(f"🔗 Попытка {attempt + 1}/{max_retries}: Проверяю {url}")

            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })

            try:
                response = await page.goto(url, wait_until="networkidle", timeout=60000)
                if not response:
                    raise Exception("No response received")

                if response.status == 404:
                    print(f"❌ Страница {url} не найдена (404)")
                    return [url, "", "0", "0", "", ""]
            except Exception as e:
                print(f"❌ Ошибка при загрузке {url}: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
                    continue
                return [url, "", "0", "0", "", ""]

            try:
                page_text = await page.inner_text("body", timeout=30000)
            except Exception:
                page_text = ""

            if "unavailable" in page.url.lower() or "this channel is private" in page_text.lower():
                print(f"❌ Канал {url} недоступен")
                return [url, "", "0", "0", "", ""]

            try:
                title = await page.title(timeout=30000)
                title = re.sub(r"Telegram:.*?(?=\s|$)", "", title).strip()
                title = re.sub(r"(@\w+|Join Group Chat|Contact|right away|If you have Telegram, you can contact)", "", title).strip()
                if not title or title.startswith("If you have Telegram"):
                    title = ""
            except Exception:
                title = ""

            page_text = re.sub(r"DOWNLOAD|VIEW IN TELEGRAM|JOIN GROUP|SEND MESSAGE|Contact @\w+ right away", "", page_text, flags=re.IGNORECASE)
            lines = [line.strip() for line in page_text.split('\n') if line.strip()]

            members = "0"
            online = "0"
            MEMBERS_RE = re.compile(r'(\d[\d\s]*)\s*(?:members|subscribers|участников|подписчиков)', re.IGNORECASE)
            ONLINE_RE = re.compile(r'(\d[\d\s]*)\s*(?:online|онлайн)', re.IGNORECASE)

            for line in lines:
                members_match = MEMBERS_RE.search(line)
                if members_match:
                    members = re.sub(r'\s', '', members_match.group(1))
                online_match = ONLINE_RE.search(line)
                if online_match:
                    online = re.sub(r'\s', '', online_match.group(1))

            description_lines = [line for line in lines if not (
                        re.search(r'^\d+\s+(?:members|subscribers|online|онлайн)', line,
                                  re.IGNORECASE) or "Preview channel" in line or any(
                    skip in line.lower() for skip in ["send message", "contact @", "if you have telegram"]))]
            description = " • ".join(description_lines)
            if not title and description_lines:
                title = description_lines[0][:50].strip() + "..." if len(description_lines[0]) > 50 else description_lines[0]

            contacts = []
            contacts.extend(re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', description))
            contacts.extend(re.findall(r'@[\w\d_]+(?!\s+right away)', description))
            urls_found = re.findall(r'https?://(?:[\w.-])+(?:/\S*)?', description)
            contacts.extend([u for u in urls_found if validators.url(u)])

            phone_patterns = [r"\+\d{1,3}[-\s]?\d{1,4}[-\s]?\d{1,4}[-\s]?\d{1,4}",
                              r"\(\d{3,4}\)[-\s]?\d{3}[-\s]?\d{2}[-\s]?\d{2}"]
            for pattern in phone_patterns:
                for match in re.findall(pattern, description):
                    try:
                        parsed = phonenumbers.parse(match, "RU")
                        if phonenumbers.is_valid_number(parsed):
                            contacts.append(phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164))
                    except:
                        continue

            contacts_str = ", ".join(c for c in contacts if c) if contacts else ""

            print(f"✅ {title}: {members} участников, {online} онлайн")
            return [url, title, members, online, description[:500], contacts_str]

        except Exception as e:
            print(f"❌ Попытка {attempt + 1}/{max_retries} не удалась для {url}: {str(e)[:100]}")
            if attempt == max_retries - 1:
                return [url, "", "0", "0", "", ""]
            await asyncio.sleep(5)


async def process_single_link(message: types.Message, url: str):
    status_message = await message.answer("🔍 Анализирую ссылку...")

    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(headless=True, args=[
                "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
                "--disable-gpu", "--disable-background-networking", "--disable-extensions",
                "--disable-sync", "--disable-default-apps", "--no-first-run"
            ])

            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                no_viewport=True
            )

            page = await context.new_page()
            page.set_default_navigation_timeout(60000)
            page.set_default_timeout(60000)

            result = await get_telegram_info(url, page, max_retries=3)
            if result[1]:
                response = (
                    f"📊 Результаты анализа:\n\n"
                    f"📌 Название: {result[1]}\n"
                    f"👥 Участников: {result[2]}\n"
                    f"🟢 Онлайн: {result[3]}\n"
                    f"📝 Описание: {result[4][:200]}...\n"
                    f"📞 Контакты: {result[5]}"
                )
            else:
                response = "❌ Не удалось получить данные по этой ссылке"
            await status_message.edit_text(response)
        except Exception as e:
            await status_message.edit_text(f"❌ Произошла ошибка: {str(e)[:200]}")
        finally:
            if 'page' in locals():
                await page.close()
            if 'context' in locals():
                await context.close()
            if browser:
                await browser.close()


async def process_csv_file(message: types.Message, csv_content: bytes):
    status_message = await message.answer("📊 Начинаю обработку файла...")
    try:
        df = pd.read_csv(io.BytesIO(csv_content), header=None, names=['url'], usecols=['url'])
        urls = df['url'].tolist()

        if len(urls) > 100:
            await message.answer("⚠️ Файл содержит более 100 ссылок. Будут обработаны только первые 100.")
            urls = urls[:100]

        results = [["Ссылка", "Название", "Участники", "Онлайн", "Описание", "Контакты"]]

        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(headless=True, args=[
                    "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
                    "--disable-gpu", "--disable-background-networking", "--disable-extensions",
                    "--disable-sync", "--disable-default-apps", "--no-first-run"
                ])

                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    no_viewport=True
                )

                for url in urls:
                    await status_message.edit_text(f"📊 Обработано: {len(results) - 1}/{len(urls)}")
                    page = await context.new_page()
                    page.set_default_navigation_timeout(60000)
                    page.set_default_timeout(60000)

                    try:
                        result = await get_telegram_info(url, page, max_retries=2)
                        results.append(result)
                    except Exception as e:
                        print(f"Ошибка при обработке {url}: {str(e)}")
                        results.append([url, "", "0", "0", "", ""])
                    finally:
                        await page.close()
                        await asyncio.sleep(2)

                await context.close()
            except Exception as e:
                print(f"Ошибка в процессе обработки CSV: {str(e)}")
            finally:
                if browser:
                    await browser.close()

        df_results = pd.DataFrame(results[1:], columns=results[0])
        output = io.BytesIO()
        df_results.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)

        result_file = BufferedInputFile(
            output.getvalue(),
            filename="results.csv"
        )
        await message.answer_document(
            result_file,
            caption="✅ Обработка завершена! Результаты в файле"
        )

    except Exception as e:
        await status_message.edit_text(f"❌ Ошибка при обработке файла: {str(e)[:200]}")


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для обогащения данных о Telegram каналах.\n\n"
        "Как использовать:\n"
        "1️⃣ Отправьте мне файл CSV со ссылками на каналы\n"
        "2️⃣ Или отправьте одну ссылку для быстрой проверки"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📚 Справка:\n\n"
        "• Отправьте CSV файл со ссылками (одна ссылка на строку)\n"
        "• Или просто отправьте ссылку на канал в чат\n"
        "• Бот вернёт: название, участников, онлайн, описание и контакты"
    )


@dp.message()
async def process_message(message: types.Message):
    try:
        if message.document and message.document.file_name.endswith('.csv'):
            file = await bot.get_file(message.document.file_id)
            downloaded_file = await bot.download_file(file.file_path)
            await process_csv_file(message, downloaded_file.read())
        elif message.text and ('t.me/' in message.text or 'telegram.me/' in message.text):
            url = re.search(r'(https?://)?t(?:elegram)?\.me/[^\s]+', message.text).group(0)
            if not url.startswith('http'):
                url = 'https://' + url
            await process_single_link(message, url)
        else:
            await message.answer(
                "📝 Отправьте мне:\n"
                "• Ссылку на Telegram канал\n"
                "• Или CSV файл со списком ссылок"
            )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")


async def main():
    print("🤖 Бот запущен")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())