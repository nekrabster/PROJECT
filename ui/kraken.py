import psutil
import os
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QFrame
)
class StatsWorker(QThread):
    stats_updated = pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        self.running = True
        self.process = psutil.Process(os.getpid())
        psutil.cpu_percent(interval=None)
        self.process.cpu_percent(interval=None)
    def run(self, *args, **kwargs):
        while self.running:
            system_cpu_usage = psutil.cpu_percent(interval=1)
            memory_info = psutil.virtual_memory()
            
            app_cpu_usage = self.process.cpu_percent(interval=None) / psutil.cpu_count()
            app_memory_info = self.process.memory_info()
            app_memory_rss_mb = app_memory_info.rss / (1024 * 1024)
            app_memory_percent = (app_memory_info.rss / memory_info.total) * 100 if memory_info.total > 0 else 0

            stats = {
                "system_cpu_usage": system_cpu_usage,
                "system_memory_percent": memory_info.percent,
                "system_memory_used": memory_info.used / (1024 * 1024),
                "system_memory_total": memory_info.total / (1024 * 1024),
                "app_cpu_usage_percent": app_cpu_usage,
                "app_memory_usage_percent": app_memory_percent,
                "app_memory_rss_mb": app_memory_rss_mb
            }
            self.stats_updated.emit(stats)
    def stop(self, *args, **kwargs):
        self.running = False
        self.wait()
class KrakenWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("kraken_window")
        self.init_ui()
        self.start_monitoring()
    def _create_stat_widget(self, label_text, *args, **kwargs):
        layout = QHBoxLayout()
        layout.setSpacing(10)
        label = QLabel(label_text)
        label.setFixedWidth(40)
        label.setStyleSheet("font-size: 14px; font-weight: bold;")
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setTextVisible(True)
        progress.setFormat("%p%")
        details_label = QLabel("...")
        details_label.setMinimumWidth(150)
        details_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        details_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(label)
        layout.addWidget(progress)
        layout.addWidget(details_label)
        widget = QWidget()
        widget.setLayout(layout) 
        return widget, progress, details_label
    def init_ui(self, *args, **kwargs):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        system_title = QLabel("Общая загрузка")
        system_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 5px;")
        main_layout.addWidget(system_title)        
        system_cpu_widget, self.system_cpu_progress, self.system_cpu_details = self._create_stat_widget("CPU")
        main_layout.addWidget(system_cpu_widget)
        system_mem_widget, self.system_mem_progress, self.system_mem_details = self._create_stat_widget("RAM")
        main_layout.addWidget(system_mem_widget)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("margin-top: 10px; margin-bottom: 10px;")
        main_layout.addWidget(separator)
        app_title = QLabel("Потребление приложения")
        app_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 5px;")
        main_layout.addWidget(app_title)
        app_cpu_widget, self.app_cpu_progress, self.app_cpu_details = self._create_stat_widget("CPU")
        main_layout.addWidget(app_cpu_widget)
        app_mem_widget, self.app_mem_progress, self.app_mem_details = self._create_stat_widget("RAM")
        main_layout.addWidget(app_mem_widget)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(spacer)
    def start_monitoring(self, *args, **kwargs):
        self.worker = StatsWorker()
        self.worker.stats_updated.connect(self.update_stats)
        self.worker.start()
    def update_stats(self, stats, *args, **kwargs):
        self.system_cpu_progress.setValue(int(stats["system_cpu_usage"]))
        self.system_cpu_details.setText(f"{stats['system_cpu_usage']:.1f}% от общей мощности")
        self.system_mem_progress.setValue(int(stats["system_memory_percent"]))
        self.system_mem_details.setText(f"{stats['system_memory_used']:.0f} / {stats['system_memory_total']:.0f} МБ")
        self.app_cpu_progress.setValue(int(stats["app_cpu_usage_percent"]))
        self.app_cpu_details.setText(f"{stats['app_cpu_usage_percent']:.1f}% от общей мощности")
        self.app_mem_progress.setValue(int(stats["app_memory_usage_percent"]))
        self.app_mem_details.setText(f"{stats['app_memory_rss_mb']:.1f} МБ")
        self.update_progress_bar_stylesheet(self.system_cpu_progress)
        self.update_progress_bar_stylesheet(self.system_mem_progress)
        self.update_progress_bar_stylesheet(self.app_cpu_progress)
        self.update_progress_bar_stylesheet(self.app_mem_progress)
    def update_progress_bar_stylesheet(self, progress_bar, *args, **kwargs):
        if progress_bar.value() > 50:
            text_color = "white"
        else:
            text_color = "black"
        progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid grey;
                border-radius: 5px;
                text-align: center;
                height: 22px;
                font-size: 12px;
            }}
            QProgressBar::chunk {{
                background-color: #3a86a3;
            }}
             QProgressBar {{
                color: {text_color};
            }}
        """)
    def closeEvent(self, event, *args, **kwargs):
        self.worker.stop()
        super().closeEvent(event)