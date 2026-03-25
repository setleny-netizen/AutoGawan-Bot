#!/usr/bin/env python3
"""
Telegram юзербот для автоматической игры в шахту
Использует библиотеку Telethon
"""

import asyncio
import logging
import sys
from typing import Optional

from telethon import TelegramClient, events
from telethon.errors import RPCError, FloodWaitError
from telethon.tl.types import Message

# Import configuration
try:
    import config
except ImportError:
    print("Error: config.py file not found!")
    print("Create config.py with your credentials")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class MiningBot:
    """Main bot class for mining game automation"""

    def __init__(self):
        self.client = TelegramClient(
            'mining_bot_session',
            config.API_ID,
            config.API_HASH,
            device_model="Python Bot",
            system_version="3.0"
        )

        self.is_running = False
        self.current_task: Optional[asyncio.Task] = None

        self.chat_id = int(config.CHAT_ID) if str(config.CHAT_ID).lstrip('-').isdigit() else config.CHAT_ID
        self.interval = config.INTERVAL_SECONDS
        self.timeout = config.MESSAGE_TIMEOUT

        self.diamond_emoji = "💎"
        self.stone_emoji = "🪨"

        logger.info(f"Bot initialized. Chat: {self.chat_id}, interval: {self.interval}s, timeout: {self.timeout}s")
        logger.info(f"Target: {self.diamond_emoji} (priority) and {self.stone_emoji}")

    async def start_client(self):
        try:
            await self.client.start(phone=config.PHONE_NUMBER)
            logger.info("Client successfully started and authorized")

            me = await self.client.get_me()
            logger.info(f"Authorized as: {me.first_name} (@{me.username}, ID: {me.id})")

            chat_entity = await self.client.get_entity(self.chat_id)
            chat_info = getattr(chat_entity, 'title', str(chat_entity.id))
            logger.info(f"Chat found: {chat_info}")

        except FloodWaitError as e:
            logger.error(f"Flood wait error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error starting client: {e}")
            raise

    async def send_mining_message(self) -> Optional[Message]:
        try:
            message = await self.client.send_message(self.chat_id, "Шахта")
            logger.info("Message 'Шахта' sent successfully")
            return message
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None

    async def get_last_message_with_buttons(self, after_id: int = 0) -> Optional[Message]:
        """Get last message with buttons after a specific message ID"""
        try:
            async for message in self.client.iter_messages(self.chat_id, limit=10):
                if message.id <= after_id:
                    continue
                if message.reply_markup:
                    return message
        except Exception as e:
            logger.error(f"Error getting last message: {e}")
        return None

    async def find_and_click_descent_button(self, message: Message) -> bool:
        try:
            if not message or not message.reply_markup:
                logger.warning("No buttons in message")
                return False

            target_text = "спуст"
            flat_buttons = []

            for row in message.buttons:
                for btn in row:
                    flat_buttons.append(btn)

            button_index = None
            for idx, btn in enumerate(flat_buttons):
                if hasattr(btn, 'text') and btn.text and target_text in btn.text.lower():
                    button_index = idx
                    break

            if button_index is None:
                logger.warning("Button 'Спуститься' not found")
                return False

            logger.info(f"Clicking button: {flat_buttons[button_index].text}")
            await message.click(button_index)
            await asyncio.sleep(3)
            logger.info("Button clicked successfully")
            return True

        except FloodWaitError as e:
            logger.warning(f"Flood wait: need to wait {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return False
        except Exception as e:
            logger.error(f"Error clicking descent button: {e}")
            return False

    async def click_resources_cyclic(self, message: Message) -> int:
        success_count = 0
        click_delay = 3

        while True:
            try:
                current_msg = await self.client.get_messages(self.chat_id, ids=message.id)
                if not current_msg or not current_msg.reply_markup:
                    logger.info("No more buttons in message")
                    break
            except Exception as e:
                logger.error(f"Error refreshing message: {e}")
                break

            found = False

            # Flatten buttons to get indices
            flat_buttons = []
            for row in current_msg.buttons:
                for btn in row:
                    flat_buttons.append(btn)

            # Diamonds first
            for idx, button in enumerate(flat_buttons):
                if button.text and self.diamond_emoji in button.text:
                    logger.info(f"Clicking 💎: {button.text} (index {idx})")
                    try:
                        await current_msg.click(idx)
                        success_count += 1
                        found = True
                        await asyncio.sleep(click_delay)
                        break
                    except Exception as e:
                        if "invalid" in str(e).lower():
                            logger.info(f"💎 already clicked, skipping")
                        else:
                            logger.error(f"Error clicking: {e}")
                        continue

            if found:
                continue

            # Stones
            for idx, button in enumerate(flat_buttons):
                if button.text and self.stone_emoji in button.text:
                    logger.info(f"Clicking 🪨: {button.text} (index {idx})")
                    try:
                        await current_msg.click(idx)
                        success_count += 1
                        found = True
                        await asyncio.sleep(click_delay)
                        break
                    except Exception as e:
                        if "invalid" in str(e).lower():
                            logger.info(f"🪨 already clicked, skipping")
                        else:
                            logger.error(f"Error clicking: {e}")
                        continue

            if not found:
                logger.info("No more valuable buttons found")
                break

        return success_count

    async def game_cycle(self) -> bool:
        logger.info("=" * 50)
        logger.info("Starting game cycle")

        msg = await self.send_mining_message()
        if not msg:
            return False

        # Wait for descent button
        descent_msg = None
        for _ in range(self.timeout):
            descent_msg = await self.get_last_message_with_buttons(after_id=msg.id)
            if descent_msg:
                clicked = await self.find_and_click_descent_button(descent_msg)
                if clicked:
                    break
            await asyncio.sleep(1)

        if not descent_msg:
            logger.warning("No descent message received")
            return False

        # Wait for NEW message with resources
        resources_msg = None
        for _ in range(self.timeout):
            candidate = await self.get_last_message_with_buttons(after_id=descent_msg.id)
            if candidate and candidate.id != descent_msg.id:
                if candidate.reply_markup:
                    resources_msg = candidate
                    break
            await asyncio.sleep(1)

        if not resources_msg:
            logger.warning("No resource message received")
            return False

        clicked_count = await self.click_resources_cyclic(resources_msg)
        logger.info(f"Clicked {clicked_count} resources in this cycle")
        logger.info("Game cycle completed")
        return True

    async def run_forever(self):
        self.is_running = True
        cycle_count = 0
        logger.info("Starting infinite game loop")

        while self.is_running:
            try:
                cycle_count += 1
                logger.info(f"=== Cycle #{cycle_count} ===")
                await self.game_cycle()
                logger.info(f"Waiting {self.interval}s until next cycle...")
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in game loop: {e}")
                await asyncio.sleep(self.interval)

    async def start_game(self) -> bool:
        if self.current_task and not self.current_task.done():
            logger.warning("Game already running!")
            return False
        self.current_task = asyncio.create_task(self.run_forever())
        logger.info("Game started")
        return True

    async def stop_game(self) -> bool:
        if not self.current_task or self.current_task.done():
            logger.warning("Game not running!")
            return False
        self.is_running = False
        try:
            await asyncio.wait_for(self.current_task, timeout=10)
        except asyncio.TimeoutError:
            self.current_task.cancel()
        self.current_task = None
        logger.info("Game stopped")
        return True

    async def setup_handlers(self):
        """Setup command handlers - рабочий вариант"""

        @self.client.on(events.NewMessage)
        async def command_handler(event):
            # Проверяем, что это текстовое сообщение
            if not event.message.text:
                return

            # Проверяем, что это команда
            if not event.message.text.startswith('/'):
                return

            command = event.message.text.lower().strip()
            logger.info(f"Received command: {command} from {event.sender_id}")

            # Обработка команд
            if command == '/start':
                success = await self.start_game()
                response = "✅ Game started! Mining 💎 first, then 🪨 every 5 minutes." if success else "⚠️ Game already running!"
                await event.reply(response)

            elif command == '/stop':
                success = await self.stop_game()
                response = "⏹️ Game stopped! Use /start to begin again." if success else "⚠️ Game not running!"
                await event.reply(response)

            elif command == '/status':
                status = "running" if self.is_running else "stopped"
                response = f"📊 Bot status: {status}\nInterval: {self.interval}s"
                await event.reply(response)

    async def run(self):
        try:
            await self.start_client()
            await self.setup_handlers()

            logger.info("=" * 50)
            logger.info("Bot ready! Use /start to begin mining.")
            logger.info("Commands: /start, /stop, /status")
            logger.info("=" * 50)

            await self.client.run_until_disconnected()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            await self.stop_game()
        except Exception as e:
            logger.error(f"Critical error: {e}", exc_info=True)
        finally:
            await self.client.disconnect()
            logger.info("Bot stopped")


def main():
    bot = MiningBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
