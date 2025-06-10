import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum, auto
class TaskType(Enum):
    MAILING = auto()
    PARSING = auto()
    SUBSCRIBE = auto()
@dataclass
class Task:
    type: TaskType
    items: List[str]
    session: Optional[str] = None
    completed: bool = False
    additional_data: Optional[Dict[str, Any]] = None
class TaskDistributor:
    def __init__(self, *args, **kwargs):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tasks: List[Task] = []
        self.sessions: List[str] = []
        self.distribution: Dict[str, List[str]] = {}
    def set_sessions(self, sessions: List[str], *args, **kwargs) -> None:
        self.sessions = sessions
        self._logger.info(f"Установлено {len(sessions)} сессий для распределения")
    def set_items(self, items: List[str], task_type: TaskType, *args, **kwargs) -> None:
        self.tasks = [
            Task(type=task_type, items=[], session=None) 
            for _ in range(len(self.sessions))
        ]
        self._distribute_items(items)
        self._logger.info(f"Распределено {len(items)} элементов между {len(self.sessions)} сессиями")
    def _distribute_items(self, items: List[str], *args, **kwargs) -> None:
        if not self.sessions:
            self._logger.warning("Нет доступных сессий для распределения")
            return
        self.distribution.clear()
        items_per_session = len(items) // len(self.sessions)
        remainder = len(items) % len(self.sessions)        
        start_idx = 0
        for i, session in enumerate(self.sessions):
            extra = 1 if i < remainder else 0
            end_idx = start_idx + items_per_session + extra            
            session_items = items[start_idx:end_idx]
            self.distribution[session] = session_items            
            if i < len(self.tasks):
                self.tasks[i].items = session_items
                self.tasks[i].session = session            
            start_idx = end_idx
            self._logger.debug(f"Сессии {session} назначено {len(session_items)} элементов")
    def get_session_items(self, session: str, *args, **kwargs) -> List[str]:
        return self.distribution.get(session, [])
    def get_distribution_info(self, *args, **kwargs) -> Dict[str, Any]:
        total_items = sum(len(items) for items in self.distribution.values())
        return {
            "total_sessions": len(self.sessions),
            "total_items": total_items,
            "items_per_session": {
                session: len(items) 
                for session, items in self.distribution.items()
            }
        }
    def mark_task_completed(self, session: str, *args, **kwargs) -> None:
        for task in self.tasks:
            if task.session == session:
                task.completed = True
                self._logger.info(f"Задача для сессии {session} помечена как выполненная")
                break
    def get_progress(self, *args, **kwargs) -> float:
        if not self.tasks:
            return 0.0
        completed = sum(1 for task in self.tasks if task.completed)
        return (completed / len(self.tasks)) * 100
distributor = TaskDistributor() 
