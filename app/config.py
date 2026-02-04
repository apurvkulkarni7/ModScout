
import os
import re
from typing import Dict
from dotenv import load_dotenv
import schedule
load_dotenv()

class AppConfig:
    def __init__(self):
        self.app_port: int = int(os.getenv("APP_PORT", 8000))
        self.hpc_username: str = os.getenv("HPC_USERNAME")
        self.hpc_ssh_key: str = os.getenv("HPC_SSH_KEY")
        
        self.systems: Dict[str, Dict[str, str]] = self._load_systems()
        self.data_dir: str = os.getenv("DATA_DIR", "./data")
        os.makedirs(self.data_dir, exist_ok=True)

        self.auto_update_database: bool = os.getenv("AUTO_UPDATE_DATABASE", "False").lower() == "True"
        self.update_schedule: str = os.getenv("UPDATE_SCHEDULE")
        self.update_day, self.update_time = self.update_schedule.split()
        self.day_map: Dict[str, any] = {
            "monday": schedule.every().monday,
            "tuesday": schedule.every().tuesday,
            "wednesday": schedule.every().wednesday,
            "thursday": schedule.every().thursday,
            "friday": schedule.every().friday,
            "saturday": schedule.every().saturday,
            "sunday": schedule.every().sunday,
        }
        self.update_job_status: Dict[str, Dict[str, str]] = self._load_job_status()

        self.data_dictionary: Dict[str, Dict] = {}

    def _load_systems(self) -> Dict[str, Dict[str, str]]:
        systems: Dict[str, Dict[str, str]] = {}
        for key, value in os.environ.items():
            match = re.match(r"SYSTEM_(\d+)_NAME", key)
            if match:
                system_index = match.group(1)
                system_name = value
                system_host = os.environ.get(f"SYSTEM_{system_index}_HOST")
                systems[system_name] = {"host": system_host}
        return systems
    
    def _load_job_status(self) -> Dict[str, Dict[str, str]]:
        job_status: Dict[str, Dict[str,str]] = {}

        for system in self.systems.keys():
            job_status[system] = {"last_run": "Never", "is_running": False}
        return job_status