import sys
import os
import asyncio
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QListWidget, 
                             QLabel, QTabWidget, QFileDialog, QComboBox)
from PyQt5.QtCore import QThread, pyqtSignal
from opentele.td import TDesktop
from opentele.tl import TelegramClient
from opentele.api import UseCurrentSession
import promo_engine

SESSIONS_DIR = "./sessions"
API_ID = 19839869
API_HASH = "7963a733802269d97dcb2234604f5801"

class ConverterWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, target_folder):
        super().__init__()
        self.target_folder = target_folder

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        if not os.path.exists(SESSIONS_DIR):
            os.makedirs(SESSIONS_DIR)

        self.log_signal.emit(f"Scanning folder: {self.target_folder}")
        success = 0
        skipped = 0

        try:
            for folder_name in os.listdir(self.target_folder):
                folder_path = os.path.join(self.target_folder, folder_name)
                tdata_path = os.path.join(folder_path, "tdata")
                key_file = os.path.join(tdata_path, "key_datas")

                if not os.path.isdir(folder_path) or not os.path.exists(tdata_path) or not os.path.exists(key_file):
                    skipped += 1
                    continue

                self.log_signal.emit(f"Processing: {folder_name}...")
                try:
                    td = TDesktop(tdata_path)
                    if not td.isLoaded() or not td.accounts:
                        self.log_signal.emit(f"  No accounts found")
                        skipped += 1
                        continue

                    account = td.accounts[0]
                    if not account.authKey:
                        self.log_signal.emit(f"  No auth key")
                        skipped += 1
                        continue

                    session_path = os.path.join(SESSIONS_DIR, folder_name)
                    client = loop.run_until_complete(
                        account.ToTelethon(session=session_path, flag=UseCurrentSession)
                    )
                    loop.run_until_complete(client.disconnect())
                    self.log_signal.emit(f"  OK: {folder_name}.session")
                    success += 1

                except Exception as e:
                    self.log_signal.emit(f"  ERROR: {e}")
                    skipped += 1

        except Exception as e:
            self.log_signal.emit(f"Fatal error: {e}")
        finally:
            self.log_signal.emit(f"=== Conversion Complete: {success} OK, {skipped} skipped ===")
            self.finished_signal.emit()

class TelegramWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.stop_event = asyncio.Event()
        self.mode = "chat"

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def emit_log(msg):
            self.log_signal.emit(msg)
            
        try:
            loop.run_until_complete(promo_engine.run_campaign(API_ID, API_HASH, emit_log, self.stop_event, mode=self.mode))
        except Exception as e:
            self.log_signal.emit(f"Runtime error: {e}")
        finally:
            loop.close()
            self.finished_signal.emit()

    def stop(self):
        self.stop_event.set()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Synthesis Promo Panel")
        self.resize(850, 600)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tg_worker = None

        self.tab_campaign = QWidget()
        self.init_campaign_tab()
        self.tabs.addTab(self.tab_campaign, "Campaign Manager")

        self.tab_import = QWidget()
        self.init_import_tab()
        self.tabs.addTab(self.tab_import, "Import tdata")

    def init_campaign_tab(self):
        layout = QHBoxLayout(self.tab_campaign)
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("Available Sessions:"))
        self.sessions_list = QListWidget()
        self.refresh_sessions_list()
        left_panel.addWidget(self.sessions_list)
        
        btn_refresh = QPushButton("Refresh List")
        btn_refresh.clicked.connect(self.refresh_sessions_list)
        left_panel.addWidget(btn_refresh)

        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Activity Log:"))
        self.campaign_log = QTextEdit()
        self.campaign_log.setReadOnly(True)
        self.campaign_log.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas;")
        right_panel.addWidget(self.campaign_log)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self.mode_selector = QComboBox()
        self.mode_selector.addItem("Chat (organic — respond to real messages)", "chat")
        self.mode_selector.addItem("Dialogue (scripted Q&A)", "dialogue")
        mode_layout.addWidget(self.mode_selector)
        mode_layout.addStretch()
        right_panel.addLayout(mode_layout)

        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("Start Campaign")
        self.btn_start.setStyleSheet("background-color: #28a745; color: white; padding: 10px; font-weight: bold;")
        self.btn_start.clicked.connect(self.start_campaign)
        
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setStyleSheet("background-color: #dc3545; color: white; padding: 10px; font-weight: bold;")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_campaign)
        
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        right_panel.addLayout(btn_layout)

        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 3)

    def init_import_tab(self):
        layout = QVBoxLayout(self.tab_import)
        layout.addWidget(QLabel("Select the root directory containing your Telegram Desktop portable folders (with tdata)."))

        controls_layout = QHBoxLayout()
        self.btn_select_folder = QPushButton("Select Folder")
        self.btn_select_folder.clicked.connect(self.select_folder)
        controls_layout.addWidget(self.btn_select_folder)

        self.btn_convert = QPushButton("Start Conversion")
        self.btn_convert.setEnabled(False)
        self.btn_convert.clicked.connect(self.start_conversion)
        controls_layout.addWidget(self.btn_convert)
        layout.addLayout(controls_layout)

        self.selected_folder_label = QLabel("No folder selected")
        layout.addWidget(self.selected_folder_label)

        self.import_log = QTextEdit()
        self.import_log.setReadOnly(True)
        self.import_log.setStyleSheet("background-color: #1e1e1e; color: #ffb86c; font-family: Consolas;")
        layout.addWidget(self.import_log)
        self.selected_folder = ""
        self.default_folder = r"C:\Users\Петрович\Desktop\tg acc"

    def refresh_sessions_list(self):
        self.sessions_list.clear()
        if os.path.exists(SESSIONS_DIR):
            for file in os.listdir(SESSIONS_DIR):
                if file.endswith(".session"):
                    self.sessions_list.addItem(file)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Profiles Folder", self.default_folder)
        if folder:
            self.selected_folder = folder
            self.selected_folder_label.setText(f"Selected: {folder}")
            self.btn_convert.setEnabled(True)

    def start_conversion(self):
        self.btn_convert.setEnabled(False)
        self.btn_select_folder.setEnabled(False)
        self.import_log.append("Initializing opentele module...")
        self.conv_worker = ConverterWorker(self.selected_folder)
        self.conv_worker.log_signal.connect(self.import_log.append)
        self.conv_worker.finished_signal.connect(self.conversion_finished)
        self.conv_worker.start()

    def conversion_finished(self):
        self.btn_convert.setEnabled(True)
        self.btn_select_folder.setEnabled(True)
        self.refresh_sessions_list()

    def start_campaign(self):
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        mode = self.mode_selector.currentData()
        mode_label = self.mode_selector.currentText()
        self.campaign_log.append(f"=== Starting Automation Engine ({mode_label}) ===")
        self.tg_worker = TelegramWorker()
        self.tg_worker.mode = mode
        self.tg_worker.log_signal.connect(self.campaign_log.append)
        self.tg_worker.finished_signal.connect(self.campaign_finished)
        self.tg_worker.start()

    def stop_campaign(self):
        if self.tg_worker:
            self.campaign_log.append("Sending stop signal... Will halt after current action.")
            self.tg_worker.stop()
            self.btn_stop.setEnabled(False)

    def campaign_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.campaign_log.append("=== Engine Stopped ===")

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", message="Server resent")
    import PyQt5
    qt_plugins = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
    if os.path.exists(qt_plugins):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = qt_plugins
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
