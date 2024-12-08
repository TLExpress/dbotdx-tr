from datetime import datetime
import asyncio
import logging

# Configure the logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UpdateIntervalManager:
    def __init__(self):
        self.tasks = {}
        logger.info("UpdateIntervalManager initialized.")

    async def unregister_task(self, task_name):
        """Unregisters a task and stops its execution."""
        if task_name in self.tasks:
            self.tasks[task_name]['stop'] = True
            await self.tasks[task_name]['task']  # Wait for task to finish
            del self.tasks[task_name]
            logger.info(f"Task {task_name} unregistered.")
        else:
            logger.warning(f"Attempted to unregister non-existent task {task_name}.")

    async def run_once(self, task_name):
        """Run a registered task once immediately."""
        if task_name in self.tasks:
            await self.tasks[task_name]['function']()
            logger.info(f"Task {task_name} run once.")
        else:
            logger.error(f"Task {task_name} is not registered.")
            raise ValueError(f"Task {task_name} is not registered.")

    async def register_task(self, task_name, seconds=None, minutes=None, hours=None, task_function=None):
        """
        Register a new periodic task.

        :param task_name: The unique name of the task
        :param seconds: A list of seconds when the task should run (None to run every second)
        :param minutes: A list of minutes when the task should run (None to run every minute)
        :param hours: A list of hours when the task should run (None to run every hour)
        :param task_function: The asynchronous function to execute
        """
        async def task_wrapper():
            while not self.tasks[task_name]['stop']:
                now = datetime.now()
                if (seconds is None or now.second in seconds) and \
                   (minutes is None or now.minute in minutes) and \
                   (hours is None or now.hour in hours):
                    await task_function()
                    logger.info(f"Task {task_name} executed at {now}.")
                await asyncio.sleep(1)

        if task_name in self.tasks:
            logger.error(f"Task {task_name} is already registered.")
            raise ValueError(f"Task {task_name} is already registered.")

        self.tasks[task_name] = {
            'stop': False,
            'function': task_function,
            'task': asyncio.create_task(task_wrapper())
        }
        logger.info(f"Task {task_name} registered.")