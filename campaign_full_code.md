# campaign — Full Source Code

--- .gitignore ---
```python
# Campaign — Telegram promotion tool

sessions/
campaign.db
*.log
*.txt
join_map.json
__pycache__/
*.pyc
.env

```

--- check_secrets.py ---
```python
"""Check for hardcoded secrets in both repos."""
import re, os

# Campaign repo
print("=== CAMPAIGN REPO ===")
with open('promo_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find API_ID and API_HASH
for m in re.finditer(r'(API_ID|API_HASH)\s*=\s*([^\n]+)', content):
    print(f'  {m.group(1)} = {m.group(2).strip()}')

# Check for any other secrets
for m in re.finditer(r'(token|secret|password|key)\s*=\s*["\']([^"\']+)', content, re.IGNORECASE):
    print(f'  {m.group(1)} = {m.group(2)[:40]}')

print()
print("=== TGGAME REPO ===")
repo_path = r'C:\555\TGgame'
for root, dirs, files in os.walk(repo_path):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'venv', '.venv')]
    for fname in files:
        if fname.endswith('.py') and fname != '__init__.py':
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    text = f.read()
                for m in re.finditer(r'(token|secret|password|api_id|api_hash|BOT_TOKEN)\s*=\s*["\']([^"\']+)', text, re.IGNORECASE):
                    print(f'  {os.path.relpath(fpath, repo_path)}: {m.group(1)} = {m.group(2)[:40]}')
            except:
                pass

# Check .env.example for what tokens are expected
print()
print("=== .ENV.EXAMPLE ===")
env_path = os.path.join(repo_path, '.env.example')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        print(f.read()[:500])

```

--- gen_fullcode.py ---
```python
"""Concatenate all core files into one markdown file."""
import os, glob

repos = [
    (r'C:\555\TGgame', 'TGgame'),
    (r'C:\555\tgacc\synthesis_promo_tool', 'campaign'),
]

for repo_path, repo_name in repos:
    out_path = os.path.join(repo_path, f'{repo_name}_full_code.md')
    exclude_dirs = {'__pycache__', '.git', '.venv', '.testvenv', 'venv', 'sessions', 
                    'data', 'alembic', '.git', '__pycache__', '.testvenv',
                    'Lib', 'Scripts', 'node_modules'}
    exclude_files = {'__init__.py', '.env', 'campaign.db', 'join_map.json',
                     f'{repo_name}_full_code.md'}
    
    with open(out_path, 'w', encoding='utf-8') as out:
        out.write(f'# {repo_name} — Full Source Code\n\n')
        
        for root, dirs, files in os.walk(repo_path):
            # Skip excluded dirs
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            # Skip hidden dirs except .github
            dirs[:] = [d for d in dirs if not d.startswith('.') or d == '.github']
            
            for fname in sorted(files):
                if fname in exclude_files:
                    continue
                if not fname.endswith('.py') and fname not in ('.gitignore', '.dockerignore', 'requirements.txt', 'run_chat.bat', 'requirements-tools.txt', 'alembic.ini'):
                    continue
                    
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, repo_path)
                
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        content = f.read()
                except:
                    continue
                
                # Skip empty or binary
                if not content.strip():
                    continue
                
                out.write(f'--- {rel} ---\n```python\n{content}\n```\n\n')
    
    print(f'{repo_name}: {out_path}')
    print(f'  Size: {os.path.getsize(out_path) / 1024:.0f} KB')
    print(f'  Lines: {sum(1 for _ in open(out_path, encoding="utf-8"))}')

```

--- main_app.py ---
```python
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

```

--- parser.py ---
```python
import asyncio, os, json
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel, Chat
from telethon.errors import FloodWaitError

API_ID = 19839869
API_HASH = "7963a733802269d97dcb2234604f5801"
TARGET = 300
MIN_M = 300
MAX_M = 3000

async def main():
    sessions = []
    for f in sorted(os.listdir("./sessions")):
        if not f.endswith(".session"):
            continue
        name = f.replace(".session", "")
        try:
            client = TelegramClient(f"./sessions/{name}", API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                sessions.append((name, client))
        except:
            pass
    if not sessions:
        print("No sessions")
        return
    print(f"Sessions: {len(sessions)}")

    collected = {}
    si = 0

    async def get_client():
        nonlocal si
        c = sessions[si % len(sessions)]
        si += 1
        return c

    keywords = [
        "game chat", "gaming group", "game discussion",
        "rpg chat", "mmo group", "pvp chat", "fps community",
        "online games", "game community", "pc games",
        "mobile games", "indie games", "strategy games",
        "action games", "survival games", "horror games",
        "racing games", "sport games", "shooter games",
        "battle royale", "open world", "sandbox games",
        "coop games", "party games", "clan chat",
        "guild chat", "players chat", "steam group",
        "game lovers", "retro games", "mmorpg chat",
        "craft games", "tanki chat", "dota chat",
        "cs chat", "valorant chat", "minecraft chat",
        "gta chat", "wot chat", "pubg chat",
        "fortnite chat", "apex chat", "warface chat",
        "terraria chat", "rust chat", "ark chat",
        "factorio chat", "rimworld chat", "subnautica chat",
        "valheim chat", "dayz chat", "project zomboid",
        "cyberpunk chat", "fallout chat", "skyrim chat",
        "witcher chat", "metro chat", "stalker chat",
        "doom chat", "borderlands chat", "diablo chat",
        "overwatch chat", "rainbow six chat", "fifa chat",
        "dead cells chat", "hollow knight chat",
        "stardew chat", "dark souls chat", "elden ring chat",
        "final fantasy chat", "monster hunter chat",
        "resident evil chat", "dead space chat",
        "total war chat", "civilization chat",
        "age of empires chat", "stellaris chat",
        "hearts of iron chat", "crusader kings chat",
        "europa universalis chat", "warhammer chat",
        "deep rock chat", "payday chat", "killing floor chat",
        "death stranding chat", "god of war chat",
        "last of us chat", "red dead chat",
        "far cry chat", "assassins creed chat",
        "ghost of tsushima chat", "spider man chat",
        "batman chat", "hogwarts legacy chat",
        "baldurs gate chat", "divinity chat",
        "disco elysium chat", "pathfinder chat",
        "xcom chat", "frostpunk chat", "satisfactory chat",
        "oxygen not included chat", "prison architect chat",
        "city skylines chat", "planet coaster chat",
        "two point chat", "banished chat",
        "graveyard keeper chat", "spiritfarer chat",
        "stray game chat", "outer wilds chat",
        "hades game chat", "transistor chat",
        "bastion chat", "pyre chat", "celeste chat",
        "ori chat", "cuphead chat", "undertale chat",
        "hollow knight chat", "dead cells chat",
        "blasphemous chat", "salt sanctuary chat",
        "hotline miami chat", "cave story chat",
        "shovel knight chat", "hyper light chat",
        "faster than light chat", "into the breach chat",
        "slay the spire chat", "darkest dungeon chat",
        "kenshi chat", "mount blade chat",
        "bannerlord chat", "warband chat",
        "kingdom come chat", "skyrim chat",
        "oblivion chat", "morrowind chat",
        "dragon age chat", "mass effect chat",
        "witcher 3 chat", "cyberpunk 2077 chat",
        "baldur chat", "neverwinter chat",
        "planescape chat", "icewind dale chat",
        "jagged alliance chat", "silent storm chat",
        "xenonauts chat", "phoenix point chat",
        "mutant year zero chat", "gears tactics chat",
        "warhammer 40k chat", "battlefleet chat",
        "battletech chat", "mechanicus chat",
        "star wars chat", "elite dangerous chat",
        "eve online chat", "star citizen chat",
        "no mans sky chat", "space engineers chat",
        "astroneer chat", "empyrion chat",
        "kerbal space chat", "dyson sphere chat",
        "satisfactory chat", "shapes chat",
        "farm together chat", "my time portia chat",
        "stardew valley chat", "harvest moon chat",
        "rune factory chat", "persona chat",
        "nier chat", "code vein chat",
        "monster hunter chat", "dauntless chat",
        "control chat", "alan wake chat",
        "titanfall chat", "wolfenstein chat",
        "quake chat", "serious sam chat",
        "bulletstorm chat", "rage chat",
        "prey chat", "dishonored chat",
        "bioshock chat", "half life chat",
        "portal chat", "left dead chat",
        "back 4 blood chat", "world war z chat",
        "dyling light chat", "dead island chat",
        "evil within chat", "silent hill chat",
        "outlast chat", "amnesia chat",
        "soma chat", "alien isolation chat",
        "subnautica below zero chat", "breathedge chat",
        "forever winter chat", "blue protocol chat",
        "throne and liberty chat", "nightingale chat",
        "v rising chat", "dinkum chat",
        "sun haven chat", "coral island chat",
        "luma island chat", "fields of mistria chat",
        "spirit island chat", "kingdom two crowns chat",
        "bear breakfast chat", "cat cafe chat",
        "travelers rest chat", "pikmin bloom chat",
        "pacific drive chat", "dredge chat",
        "highfleet chat", "overload chat",
        "descent chat", "sublevel zero chat",
        "lost judgment chat", "like a dragon chat",
        "yakuza chat", "judgment chat",
        "chrono trigger chat", "secret of mana chat",
        "octopath traveler chat", "bravely default chat",
        "fire emblem chat", "shin megami chat",
        "dragon quest chat", "atelier chat",
        "story of seasons chat", "harvestella chat",
        "rune factory chat", "ni no kuni chat",
        "dragon dogma chat", "kingdoms of amalur chat",
        "fable chat", "gothic chat",
        "risen chat", "elex chat",
        "greedfall chat", "technomancer chat",
        "bound by flame chat", "mars war logs chat",
        "vampyr chat", "plague tale chat",
        "life is strange chat", "telltale chat",
        "walking dead telltale chat", "wolf among us chat",
        "batman telltale chat", "game of thrones telltale chat",
        "minecraft story mode chat", "borderlands telltale chat",
        "the exopancreas chat", "as dusk falls chat",
        "road 96 chat", "until dawn chat",
        "dark pictures chat", "quarry chat",
        "detroit become human chat", "heavy rain chat",
        "beyond two souls chat", "indigo prophecy chat",
        "omori game chat", "oneshot chat",
        "to the moon chat", "finding paradise chat",
        "impostor factory chat", "undertale yellow chat",
        "deltarune chat", "everhood chat",
        "chicory chat", "wandersong chat",
        "carto game chat", "alba wildlife chat",
        "unpacking chat", "townscaper chat",
        "islanders chat", "dorfromantik chat",
        "mini motorways chat", "mini metro chat",
        "besiege chat", "poly bridge chat",
        "kerbal space chat", "simple planes chat",
        "stormworks chat", "trailmakers chat",
        "scrap mechanic chat", "main assembly chat",
        "from the depths chat", "space engineers chat",
        "medieval engineers chat", "crossout chat",
        "robocraft chat", "terratech chat",
        "besiege chat", "trailmakers chat",
        "scrap mechanic chat", "my summer car chat",
        "mon bazou chat", "beamng drive chat",
        "assetto corsa chat", "iracing chat",
        "forza horizon chat", "need for speed chat",
        "grid game chat", "dirt rally chat",
        "wrc game chat", "f1 game chat",
        "moto gp chat", "ride game chat",
        "trackmania chat", "trials rising chat",
        "steep game chat", "shredders chat",
        "snowrunner chat", "mudrunner chat",
        "spintires chat", "farming simulator chat",
        "bus simulator chat", "euro truck chat",
        "american truck chat", "train simulator chat",
        "derail valley chat", "cities skylines chat",
        "workers resources chat", "transport fever chat",
        "factorio chat", "captain of industry chat",
        "foundation game chat", "kingdoms reborn chat",
        "before we leave chat", "terra nil chat",
        "ikonei island chat", "lil gator game chat",
        "smushi come home chat", "toem chat",
        "birb game chat", "a short hike chat",
        "haven park chat", "hokko life chat",
        "reus game chat", "garden life chat",
        "powerwash simulator chat", "house flipper chat",
        "pc building simulator chat", "car mechanic chat",
        "thief simulator chat", "gas station simulator chat",
        "internet cafe simulator chat", "airport ceo chat",
        "tower tycoon chat", "raft game chat",
        "stranded deep chat", "green hell chat",
        "the forest chat", "sons of forest chat",
        "grounded chat", "smalland chat",
        "valheim chat", "conan exiles chat",
        "scum chat", "dayz chat",
        "deadside chat", "escapists chat",
        "the long dark chat", "this war of mine chat",
        "frostpunk chat", "i am future chat",
        "dysmantle chat", "cataclysm dda chat",
        "neo scavenger chat", "project zomboid chat",
        "state of decay chat", "dont starve chat",
        "oxygen not included chat", "raft world chat",
        "cliff empire chat", "crashlands chat",
        "jydge chat", "dead cells chat",
        "skul hero chat", "hades chat",
        "curse dead gods chat", "atomicrops chat",
        "enter gungeon chat", "binding isaac chat",
        "the end is nigh chat", "super meat boy chat",
        "celeste chat", "n++ chat",
        "speedrunners chat", "move or die chat",
        "ultimate chicken chat", "gang beasts chat",
        "human fall flat chat", "among us chat",
        "fall guys chat", "pummel party chat",
        "boomerang fu chat", "tricky towers chat",
        "overcooked chat", "tools up chat",
        "moving out chat", "plate up chat",
        "cook serve delicious chat", "battleblock theater",
        "castle crashers chat", "pico park chat",
        "heave ho chat", "totally reliable chat",
        "i am fish chat", "rain world chat",
        "death door chat", "tunic chat",
        "eastward chat", "sea of stars chat",
        "chain echoes chat", "chained echoes chat",
        "crosscode chat", "unsighted chat",
        "hyper light drifter chat", "solar ash chat",
        "fenglee chat", "abzu chat",
        "journey game chat", "sky children chat",
        "flower game chat", "gris chat",
        "neva game chat", "planet of lana chat",
        "somerville chat", "inside game chat",
        "limbo game chat", "cocoon game chat",
        "little nightmares chat", "stray game chat",
        "astros playroom chat", "sackboy chat",
        "ratchet clank chat", "jak and daxter chat",
        "sly cooper chat", "crash bandicoot chat",
        "spyro chat", "medievil chat",
        "tony hawk chat", "skate game chat",
        "session skate chat", "skater xl chat",
        "lonely mountains chat", "descenders chat",
        "riders republic chat", "steep chat",
        "shredders chat", "grand mountain chat",
        "art of rally chat", "dirt chat",
        "wreckfest chat", "beamng chat",
        "teardown chat", "paint the town red chat",
        "ragdoll cannon chat", "people playground chat",
        "karateka chat", "duken nukem chat",
        "shadow warrior chat", "strife chat",
        "heretic chat", "hexen chat",
        "blood game chat", "ion fury chat",
        "dusk chat", "amid evil chat",
        "prodeus chat", "ultrakill chat",
        "turbo overkill chat", "boltgun chat",
        "hrot chat", "postal chat",
        "nightmare reaper chat", "cultic chat",
        "selaco chat", "minecraft dungeons chat",
        "minecraft legends chat", "hytale chat",
        "trover saves chat", "accounting plus chat",
        "boneworks chat", "bone lab chat",
        "half life alyx chat", "vr chat",
        "rec room chat", "gorilla tag chat",
        "echo vr chat", "pavlov vr chat",
        "population one chat", "walkabout golf chat",
        "beat saber chat", "synth riders chat",
        "pistol whip chat", "superhot vr chat",
        "job simulator chat", "vacation simulator chat",
        "i expect you to die chat", "the room vr chat",
        "red matter chat", "asgards wrath chat",
        "lone echo chat", "stormland chat",
        "skyrim vr chat", "fallout 4 vr chat",
        "no mans sky vr chat", "elite dangerous vr chat",
        "project wingman chat", "ace combat chat",
        "star wars squadron chat", "space engineers chat",
        "dual universe chat", "starbase chat",
        "avian chat", "space haven chat",
        "cosmoteer chat", "highfleet chat",
        "nebulous fleet chat", "rule the waves chat",
        "commander the great war chat", "ultimate admiral chat",
        "war on the sea chat", "cold waters chat",
        "sonar tactical chat", "uboat game chat",
        "wolfpack game chat", "silent hunter chat",
        "dangerous waters chat", "naval action chat",
        "world of warships chat", "battle stations chat",
        "atlantic fleet chat", "task force admiral chat",
        "turboprop flight chat", "fsx flight chat",
        "msfs flight chat", "x plane chat",
        "aerofly chat", "war thunder chat",
        "il2 sturmovik chat", "dcs world chat",
        "falcon bms chat", "vtol vr chat",
        "flight sim chat", "honeycomb flight chat",
        "yuzu emulator chat", "ryujinx chat",
        "rpcs3 chat", "cemu chat",
        "dolphin emulator chat", "pcsx2 chat",
        "duckstation chat", "ppsspp chat",
        "retroarch chat", "mame chat",
        "scummvm chat", "dosbox chat",
        "exagear chat", "winlator chat",
        "skyline emulator chat", "yuzu early chat",
        "strato emulator chat", "vita3k chat",
        "xenia chat", "xemu chat",
        "mGBA chat", "melonDS chat",
        "desmume chat", "citra chat",
        "android emulator chat", "pc emulator chat",
        "godot engine chat", "unity engine chat",
        "unreal engine chat", "cryengine chat",
        "source engine chat", "game maker chat",
        "rpg maker chat", "renpy chat",
        "twine game chat", "bitsy game chat",
        "pico 8 chat", "tic 80 chat",
        "löve2d chat", "pygame chat",
        "gamedev chat", "indiedev chat",
        "solo dev chat", "game jam chat",
        "ludum dare chat", "global game jam chat",
        "itch io chat", "steam dev chat",
        "gog games chat", "epic games chat",
        "game pass chat", "xbox game pass chat",
        "ps plus chat", "psn chat",
        "nintendo online chat", "nso chat",
        "retro games chat", "old games chat",
        "abandonware chat", "roms chat",
        "emulation chat", "emulator chat",
        "pc gaming chat", "console gaming chat",
        "hardware gaming chat", "setup gaming chat",
        "battlestation chat", "desk setup chat",
        "mechanical keyboard chat", "mouse chat",
        "headset chat", "monitor chat",
        "gaming chair chat", "rgb chat",
        "water cooling chat", "pc build chat",
        "should i buy chat", "game sale chat",
        "game deal chat", "game discount chat",
        "free game chat", "game giveaway chat",
        "steam sale chat", "gog sale chat",
        "epic free chat", "prime gaming chat",
        "humble bundle chat", "fanatical chat",
        "green man gaming chat", "game key chat",
        "game trade chat", "steam trade chat",
        "steam market chat", "csgo skin chat",
        "dota trade chat", "tf2 trade chat",
        "game collect chat", "physical game chat",
        "game case chat", "steelbook chat",
        "retro collect chat", "sealed game chat",
        "game room chat", "man cave chat",
        "game night chat", "party game night chat",
        "board game night chat", "ttrpg chat",
        "dungeons dragons chat", "pathfinder ttrpg chat",
        "call of cthulhu rpg chat", "cyberpunk red chat",
        "shadowrun ttrpg chat", "warhammer rpg chat",
        "blades in dark chat", "pbta chat",
        "dnd 5e chat", "dnd 2024 chat",
        "dnd 3.5 chat", "dnd 4e chat",
        "dnd adventure chat", "dnd campaign chat",
        "dnd homebrew chat", "dnd character chat",
        "dnd dice chat", "dnd mini chat",
        "warhammer 40k ttrpg chat", "age of sigmar chat",
        "warhammer fantasy chat", "kill team chat",
        "warcry chat", "necromunda chat",
        "blood bowl chat", "battle tech ttrpg chat",
        "starfinder chat", "traveler rpg chat",
        "savage worlds chat", "gurps chat",
        "call of cthulhu 7e chat", "delta green chat",
        "mothership rpg chat", "mork borg chat",
        "into the odd chat", "electric bastionland chat",
        "cairn rpg chat", "knave rpg chat",
        "ironsworn chat", "starforged chat",
        "dungeon world chat", "monster of week chat",
        "masks rpg chat", "urban shadows chat",
        "spire rpg chat", "heart rpg chat",
        "lancer rpg chat", "icon rpg chat",
        "fabula ultima chat", "breaker chat",
        "draw steel chat", "dungeon crawl classics chat",
        "shadowdark chat", "osr chat",
        "old school essentials chat", "basic fantasy chat",
        "low fantasy gaming chat", "beyond the wall chat",
        "through sunken lands chat", "fever swamp chat",
        "dolmenwood chat", "hot springs island chat",
        "neverland rpg chat", "oz rpg chat",
        "mausritter chat", "cairn rpg chat",
        "into the odd chat", "electric bastionland chat",
        "knave rpg chat", "boil rpg chat",
        "trophy rpg chat", "cbr+pnk chat",
        "neon city overdrive chat", "carbon grey chat",
        "cyberpunk red chat", "cyberpunk 2020 chat",
        "shadowrun 5e chat", "shadowrun 6e chat",
        "shadowrun anarchy chat", "the sprawl chat",
        "vektas cyberpunk chat", "hard wired island chat",
        "headspace rpg chat",         "technoir chat",
        # more keywords to reach 300
        "gaming lounge", "game servers", "multiplayer community",
        "game trade", "game giveaways", "game boost",
        "game leveling", "gaming news", "game updates",
        "game patch", "game launcher", "game client",
        "game beta", "game early access", "game demo",
        "game preorder", "game launch", "game release",
        "game DLC", "game expansion", "game season pass",
        "game battle pass", "game microtransaction",
        "game soundtrack", "game art", "game concept",
        "game design", "game level design",
        "game writing", "game narrative",
        "game voice acting", "game mo-cap",
        "game animation", "game modeling",
        "game texturing", "game rigging",
        "game vfx", "game shader",
        "game optimization", "game port",
        "game remaster", "game remake",
        "game remastered", "game collection",
        "game compilation", "game anthology",
        "game codex", "game wiki",
        "game guide", "game walkthrough",
        "game tutorial", "game training",
        "game practice", "game warmup",
        "game scrim", "game tournament",
        "game league", "game division",
        "game season", "game playoffs",
        "game finals", "game qualifiers",
        "game bracket", "game ladder",
        "game ranked", "game unranked",
        "game casual", "game competitive",
        "game pro", "game semi-pro",
        "game amateur", "game beginner",
        "game intermediate", "game advanced",
        "game expert", "game veteran",
        "game newcomer", "game rookie",
        "game main chat", "game general chat",
        "game off-topic", "game chill chat",
        "game vc", "game voice chat",
        "game text chat", "game ingame chat",
        "game lobby chat", "game party chat",
        "game team chat", "game group chat",
        "game global chat", "game world chat",
        "game regional chat", "game country chat",
        "game city chat", "game area chat",
        "game language chat", "game chat ru",
        "game chat en", "game chat fr",
        "game chat de", "game chat es",
        "game chat pt", "game chat it",
        "game chat pl", "game chat ua",
        "game chat by", "game chat cn",
        "game chat jp", "game chat kr",
        "game community ru", "game community en",
        "game chat russia", "game chat ukraine",
        "game chat europe", "game chat asia",
        "game chat america", "game chat world",
        "game social", "game network",
        "game feed", "game timeline",
        "game board", "game forum",
        "game chate", "gaming chate",
        "игровой топик", "игровая ветка",
        "обсуждение игр чат", "гейминг общение",
        "игровой форум", "чат по играм общий",
        "игры на пк чат", "игры на консолях чат",
        "онлайн игры обсуждение", "многопользовательские игры",
        "геймерский тг", "чат геймеров тг",
        "игровые новости чат", "игровая индустрия",
        "разработка игр чат", "геймдев чат",
        "игровой маркет чат", "дота общий чат",
        "кс общий чат", "майнкрафт общий чат",
        "арена батл чат", "королевская битва чат",
        "выживач чат", "стратегии реального времени",
        "пошаговые стратегии чат", "рогалики чат",
        "квесты чат", "головоломки чат",
        "шутеры от первого лица", "шутеры от третьего лица",
        "симуляторы чат", "спортивные игры чат",
        "гонки чат", "файтинги чат",
        "хорроры на выживание", "стелс игры чат",
        "экшн адвенчура чат", "рпг чат общий",
        "мморпг чат общий", "песочница чат",
        "игровой клуб чат", "геймерское комьюнити",
        "team fortress chat", "tf2 chat",
        "left 4 dead chat", "l4d2 chat",
        "portal 2 chat", "half life 2 chat",
        "counter strike 1.6 chat", "cs 1.6 chat",
        "cs source chat", "cs 2 chat",
        "team fortress 2 chat", "tf2 trade chat",
        "dota 2 chat russian", "dota 2 chat english",
        "league of legends chat ru", "lol ru chat",
        "world of warcraft ru chat", "wow ru chat",
        "warcraft 3 chat", "wc3 chat",
        "starcraft 2 chat", "sc2 chat",
        "diablo 2 chat", "diablo 3 chat",
        "diablo 4 chat", "overwatch 2 chat",
        "pubg mobile chat", "pubg pc chat",
        "fortnite ru chat", "fortnite en chat",
        "apex legends ru chat", "apex ru chat",
        "valorant ru chat", "valorant en chat",
        "cs go chat", "cs 2 ru chat",
        "rust ru chat", "dayz ru chat",
        "minecraft ru chat", "minecraft anarchy chat",
        "minecraft survival chat", "gta 5 rp chat",
        "samp chat", "gta samp chat",
        "crmp chat", "minecraft mmo chat",
        "wot blitz chat", "world of tanks blitz chat",
        "war thunder chat ru", "war thunder chat en",
        "world of warships chat", "world of warships blitz chat",
        "wot console chat", "mobile legends chat",
        "wild rift chat", "cod mobile chat",
        "cod warzone chat", "cod modern warfare chat",
        "battlefield 2042 chat", "battlefield 1 chat",
        "battlefield 5 chat", "battlefield 4 chat",
        "rainbow six siege chat", "r6 siege chat",
        "r6 ru chat", "division 2 chat",
        "destiny 2 chat", "destiny 2 ru chat",
        "warframe chat", "warframe ru chat",
        "path of exile chat", "poe ru chat",
        "poe trade chat", "lost ark chat",
        "lost ark ru chat", "new world chat",
        "new world ru chat", "throne and liberty chat",
        "black desert chat", "bdo chat",
        "eve online ru chat", "albion online chat",
        "albion ru chat", "runescape chat",
        "oldschool runescape chat", "runescape osrs chat",
        "final fantasy 14 chat", "ff14 chat",
        "ff14 ru chat", "world of warcraft classic chat",
        "wow classic chat", "wow wotlk chat",
        "wow retail chat", "wow dragonflight chat",
        "wow the war within chat", "guild wars 2 chat",
        "gw2 chat", "elder scrolls online chat",
        "eso chat", "swtor chat",
        "star wars old republic chat", "ffxi chat",
        "FFXI chat", "maplestory chat",
        "maplestory reboot chat", "ragnarok online chat",
        "ro chat", "tree of savior chat",
        "soulworker chat", "closers chat",
        "vindictus chat", "tera chat",
        "neverwinter online chat", "skyforge chat",
        "allods online chat", "perfect world chat",
        "jade dynasty chat", "lineage 2 chat",
        "l2 chat", "l2 ru chat",
        "lineage 2 classic chat", "lineage 2 essence chat",
        "aion chat", "aion classic chat",
        "metin2 chat", "mu online chat",
        "mu legend chat", "conquer online chat",
        "4story chat", "12 sky chat",
        "9 dragons chat", "archage chat",
        "bless unleashed chat", "territory chat",
        "revelation online chat", "saint seiya chat",
        "cosmic break chat", "gundam evolution chat",
        "overprime chat", "predecessor chat",
        "paragon chat", "smite chat",
        "smite ru chat", "paladins chat",
        "paladins ru chat", "battlerite chat",
        "battlegrounds chat", "pubg chat",
        "playerunknown chat", "ring of elysium chat",
        "spellbreak chat", "the cycle chat",
        "hunt showdown chat", "hunt showdown ru chat",
        "escape from tarkov chat", "tarkov chat",
        "eft chat", "tarkov ru chat",
        "arena breakout chat", "marathon chat",
        "delta force chat", "delta force hawk chat",
        "insurgency chat", "insurgency sandstorm chat",
        "hell let loose chat", "post scriptum chat",
        "squad game chat", "squad ru chat",
        "arma 3 chat", "arma reforger chat",
        "dayz standalone chat", "scum chat",
        "deadside chat", "miscreated chat",
        "the isle chat", "path of titans chat",
        "beast of bermuda chat", "identity chat",
        "rust console chat", "7 days to die chat",
        "7dtd chat", "conan exiles chat",
        "valheim ru chat", "v rising ru chat",
        "grounded chat", "smalland chat",
        "green hell chat", "the forest chat",
        "sons of the forest chat", "subnautica below zero chat",
        "raft chat", "stranded deep chat",
        "state of decay 2 chat", "state of decay 3 chat",
        "dying light 2 chat", "dead island 2 chat",
        "dead rising chat", "zombie army chat",
        "world war z chat", "back 4 blood chat",
        "left 4 dead 2 chat", "killing floor 2 chat",
        "payday 2 chat", "payday 3 chat",
        "raiders chat", "ready or not chat",
        "swat 4 chat", "zero hour chat",
        "ground branch chat", "bodycam chat",
        "unrecord chat", "operation flashpoint chat",
        "ghost recon chat", "rainbow six chat",
        "splinter cell chat", "metal gear solid chat",
        "hitman chat", "deadbolt chat",
        "hotline miami 2 chat", "katana zero chat",
        "my friend pedro chat", "sanctum 2 chat",
        "dungeon defenders chat", "orc must die chat",
        "synthetik chat", "nuclear throne chat",
        "enter the gungeon chat", "binding of isaac chat",
        "vampire survivors chat", "broforce chat",
        "castle crashers chat", "battleblock theater chat",
        "pico park chat", "ultimate chicken horse chat",
        "gang beasts chat", "human fall flat chat",
        "moving out chat", "overcooked 2 chat",
        "plate up chat", "cook serve delicious 3 chat",
        "tools up chat", "boomerang fu chat",
        "tricky towers chat", "heave ho chat",
        "totally reliable chat", "among us chat",
        "fall guys chat", "pummel party chat",
        "mario party chat", "nintendo switch sports chat",
        "wii sports chat", "ring fit adventure chat",
        "just dance chat", "fitness boxing chat",
        "beatsaber chat", "synth riders chat",
        "pistol whip chat", "audica chat",
        "oh shape chat", "superhot chat",
        "half life alyx chat", "boneworks chat",
        "bone lab chat", "blade sorcery chat",
        "battle talent chat", "h3vr chat",
        "hot dogs horseshoes chat", "walkabout mini golf chat",
        "golf plus chat", "eleven table tennis chat",
        "contractors chat", "pavlov chat",
        "onward chat", "into the radius chat",
        "survival nation chat", "saints sinners chat",
        "asgards wrath 2 chat", "medal of honor chat",
        "lone echo 2 chat", "stormland chat",
        "defector chat", "i expect you to die 2 chat",
        "the room vr chat", "red matter 2 chat",
        "horizon call mountain chat", "gran turismo 7 chat",
        "gt7 chat", "forza motorsport chat",
        "forza horizon 5 chat", "need for speed unbound chat",
        "the crew motorfest chat", "test drive unlimited chat",
        "assetto corsa competizione chat", "acc chat",
        "iracing chat", "r factor 2 chat",
        "automobilista 2 chat", "dirt rally 2.0 chat",
        "ea sports wrc chat", "f1 23 chat",
        "f1 24 chat", "moto gp 24 chat",
        "ride 5 chat", "mx vs atv chat",
        "descenders chat", "lonely mountains downhill chat",
        "riders republic chat", "steep chat",
        "shredders chat", "tricky chat",
        "session skate sim chat", "skater xl chat",
        "tony hawk pro skater chat",
        "owlboy chat", "iconoclasts chat",
        "furi chat", "thomas was alone chat",
        "fez chat", "braid chat",
        "limbo chat", "inside chat",
        "little nightmares 2 chat", "little nightmares 3 chat",
        "unravel 2 chat", "sackboy chat",
        "it takes two chat", "a way out chat",
        "brothers tale chat", "split fiction chat",
        "ashes cricket chat", "cricket 24 chat",
        "ea sports fc 25 chat", "fc 25 chat",
        "ea sports fc 24 chat", "pro evolution soccer chat",
        "e football chat", "football manager 24 chat",
        "fm 24 chat", "madden nfl 25 chat",
        "nba 2k25 chat", "mlb the show 24 chat",
        "nhl 24 chat", "pga tour 2k23 chat",
        "ea sports pga tour chat", "wwe 2k24 chat",
        "wwe 2k25 chat", "aew fight forever chat",
        "ufc 5 chat", "undisputed boxing chat",
        "street fighter 6 chat", "mortal kombat 1 chat",
        "tekken 8 chat", "guilty gear strive chat",
        "dragon ball fighterz chat", "dragon ball sparking zero chat",
        "naruto storm connections chat", "one piece pirate warriors chat",
        "jump force chat", "my hero ultra rumble chat",
        "demon slayer hinokami chat", "soulcalibur 6 chat",
        "dead or alive 6 chat", "blazblue centralfiction chat",
        "under night inbirth chat", "melty blood type lumina chat",
        "granblue fantasy versus chat", "dnf duel chat",
        "king of fighters 15 chat", "samurai shodown chat",
        "virtua fighter 5 chat", "multi versus chat",
        "nickelodeon all star brawl chat", "brawlhalla chat",
        "platform fighter chat", "smash bros chat",
        "rivals of aether chat", "fraymakers chat",
        "slap city chat", "bacon may die chat",
        "arrow chat", "sniper elite 5 chat",
        "sniper ghost warrior chat", "sniper contracts 2 chat",
        "zombie army 4 chat", "strange brigade chat",
        "world war z aftermath chat", "killing floor 3 chat",
        "dead island riptide chat", "escape dead island chat",
        "plants zombies chat", "pvz battle neighborville chat",
        "garden warfare chat", "pvz gw2 chat",
        "oceanhorn chat", "battle chasers nightwar chat",
        "south park fractured chat", "south park stick truth chat",
        "lego game chat", "lego star wars chat",
        "lego harry potter chat", "lego batman chat",
        "lego city undercover chat", "lego marvel chat",
        "lego dc villains chat", "lego the incredibles chat",
        "skylanders chat", "disney infinity chat",
        "amiibo chat", "power pros chat",
        "j stars victory chat", "jump legends chat",
        "gundam versus chat", "gundam evolution chat",
        "gundam breaker 4 chat", "armored core 6 chat",
        "daemon x machina chat", "m.a.s.s. builder chat",
        "war tech fighters chat", "hawken chat",
        "zone of enders chat", "anubis zone enders chat",
        "star fox chat", "starlink battle chat",
        "chorus game chat", "ever space 2 chat",
        "everspace chat", "rebel galaxy chat",
        "elite dangerous odyssey chat", "x4 foundations chat",
        "x rebirth chat", "spacebourne 2 chat",
        "starsector chat", "nebulous fleet command chat",
        "rule the waves 3 chat", "commander battle chat",
        "ultimate general chat", "grand tactician chat",
        "strategic mind chat", "decisive campaigns chat",
        "order of battle chat", "panzer corps 2 chat",
        "unity of command 2 chat", "strategic command chat",
        "world conqueror 4 chat", "age of civilizations chat",
        "supremacy 1914 chat", "call of war chat",
        "conflict of nations chat", "war nations chat",
        "iron order 1918 chat", "foxhole chat",
        "warno game chat", "wargame red dragon chat",
        "steel division 2 chat", "broken arrow chat",
        "regiments game chat", "syrian warfare chat",
        "command modern operations chat", "combat mission chat",
        "graviteam tactics chat", "armored brigade chat",
        "panzer marshal chat", "africa corps chat",
        "desert war chat", "toppoli chat",
        "ещё игры чат", "игровой чат ру",
        "общий игровой чат", "чатик для игр",
        "нейросеть игры чат", "ai games chat",
        "chat gpt games chat", "искуственный интеллект игры",
        "top 100 games chat", "game awards chat",
        "ichi io game chat", "game jam chat",
        "тыжпрограммист чат", "айти игры чат",
        "игровой канал чат", "топ игр 2024 чат",
        "топ игр 2025 чат", "game of the year chat",
        "goty chat", "steam awards chat",
        "игровая премия чат", "e3 chat",
        "gamescom chat", "tokyo game show chat",
        "nintendo direct chat", "state of play chat",
        "xbox showcase chat", "ubisoft forward chat",
        "ea play chat", "summer game fest chat",
        "geoff keighley chat", "the game awards chat",
        "раздача игр чат", "бесплатные игры чат",
        "скидки на игры чат", "распродажа steam чат",
        "steam winter sale chat", "steam summer sale chat",
        "gog sale chat", "epic games sale chat",
        "game trade russia chat", "обмен игр чат",
        "барахолка игр чат", "игровой маркетплейс чат",
        "steam аккаунты чат", "game keys chat",
        "steam ключи чат", "origin ключи чат",
        "uplay ключи чат", "epic ключи чат",
        "gog ключи чат", "steam gifts chat",
        "steam обмен чат", "steam трейд чат",
        "csgo скины чат", "dota 2 скины чат",
        "tf2 скины чат", "rust скины чат",
        "буст чат", "game boosting chat",
        "калибровка чат", "mmr boost chat",
        "elo boost chat", "rank boost chat",
        "game coaching chat", "тренер по играм чат",
        "game trainer chat", "читы для игр чат",
        "game mods chat", "моды для игр чат",
        "game patches chat", "фиксы игр чат",
        "game cracks chat", "репаки игр чат",
        "пиратка чат", "пиратские игры чат",
        "game repacks chat", "fitgirl repack chat",
        "dodi repack chat", "xatab repack chat",
        "igruha repack chat", "chovka repack chat",
        "online fix chat", "fixer chat",
        "goldberg emu chat", "steam emu chat",
        "game update chat", "обновление игр чат",
    ]

    for kw_idx, keyword in enumerate(keywords, 1):
        if len(collected) >= TARGET:
            print(f"Reached {TARGET}, stopping.")
            break

        name, client = await get_client()
        try:
            result = await client(SearchRequest(q=keyword, limit=200))
        except FloodWaitError as e:
            print(f"  Flood {e.seconds}s on {name}, skipping")
            continue
        except Exception as e:
            print(f"  Error on {name}: {e}")
            continue

        for chat in result.chats:
            if len(collected) >= TARGET:
                break
            is_group = isinstance(chat, Channel) and getattr(chat, 'megagroup', False)
            is_chat = isinstance(chat, Chat)
            if not (is_group or is_chat):
                continue
            uname = getattr(chat, 'username', None)
            if not uname or uname in collected:
                continue

            count = getattr(chat, 'participants_count', None)
            if count is None and isinstance(chat, Channel):
                try:
                    full = await client(GetFullChannelRequest(chat))
                    count = getattr(full.full_chat, 'participants_count', None)
                except:
                    pass
                await asyncio.sleep(1.5)

            if count is not None and MIN_M <= count <= MAX_M:
                collected[uname] = count
                with open("chats.txt", "w", encoding="utf-8") as f:
                    for u in sorted(collected.keys()):
                        f.write(f"{u}\n")
                print(f"  + {uname} ({count}) [{len(collected)}/{TARGET}]")

        if kw_idx % 25 == 0:
            print(f"[{kw_idx}/{len(keywords)}] {len(collected)} chats")

    for _, client in sessions:
        try:
            await client.disconnect()
        except:
            pass

    print(f"\nDone: {len(collected)} chats (300-3000 members)")

asyncio.run(main())

```

--- promo_engine.py ---
```python
import asyncio
import random
import os
import json
import re
import sqlite3
import time
import threading
from datetime import datetime
from urllib.parse import quote
import httpx
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty

JOIN_MAP_FILE = "join_map.json"

# ─── Gemini integration ────────────────────────────────────────────────────────

GEMINI_ENDPOINT = "http://localhost:8081/v1/chat/completions"
GEMINI_SYSTEM_PROMPT = (
    "Ты обычный пользователь в Telegram-чате. Отвечай естественно, кратко, как живой человек.\n"
    "Правила:\n"
    "- Только русский язык, 1-3 коротких предложения\n"
    "- Если хочешь сказать несколько мыслей — раздели их пустой строкой (бот отправит как отдельные сообщения)\n"
    "- Без эмодзи, без звёздочек, без форматирования\n"
    "- Если тема разговора — игры, досуг, свободное время — ненавязчиво упомяни "
    "'Synthesis game bot' (текстовый крафт-бот в Telegram)\n"
    "- Иначе просто поддержи разговор нейтрально\n"
    "- Не звучи как реклама, не повторяйся, не используй шаблонные фразы"
)

GEMINI_CONTEXT_PROMPT = (
    "Вот последние сообщения в чате (\"пользователь\" — другие люди, \"я\" — это ты). "
    "Ответь одним сообщением на ситуацию естественно."
)

async def generate_gemini_response(last_messages_text: str) -> str | None:
    """Generate a contextual reply using the local Gemini proxy. Returns None on failure."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(GEMINI_ENDPOINT, json={
                "model": "gemini-3.5-flash",
                "messages": [
                    {"role": "system", "content": GEMINI_SYSTEM_PROMPT},
                    {"role": "user", "content": f"{GEMINI_CONTEXT_PROMPT}\n\n---\n{last_messages_text}"}
                ],
                "temperature": 0.9,
                "max_tokens": 120
            })
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                # Remove quotes if Gemini wrapped the answer
                text = text.strip('"\'»«').strip()
                return text if text else None
    except Exception:
        return None
    return None

# ─── Spintax ─────────────────────────────────────────────────────────────────

def render_spintax(text: str) -> str:
    """Render spintax: {var1|var2|var3} picks one randomly.
    Supports escaping via backslash+brace and nesting one level."""
    def replace(m):
        opts = [o.strip() for o in m.group(1).split("|")]
        rendered = random.choice(opts)
        # recursively render nested spintax in the chosen option
        while "{" in rendered:
            rendered = re.sub(r"\{([^{}]+)\}", lambda mm: random.choice([o.strip() for o in mm.group(1).split("|")]), rendered)
        return rendered
    return re.sub(r"\{([^{}]+)\}", replace, text)

# ─── Spintax questions ───────────────────────────────────────────────────────

QUESTION_SPINTAX = (
    "Блин, {скучно|тоска|скукота|пипец как скучно}. "
    "Посоветуйте {какую-нибудь|какую|хоть какую-то} "
    "{залипалку текстовую|текстовую игру|игру в телеге}, "
    "{только чтоб|лишь бы|главное чтобы} без доната {жесткого|бешеного|сильного}."
)

# ─── Spintax answers ─────────────────────────────────────────────────────────

ANSWER_SPINTAX = (
    "Вбей в поиск телеги Synthesis game bot. "
    "Там {механика крафта прикольная|крафт прикольный|интересная механика крафта}, "
    "{сижу второй день собираю предметы|третий день играю|уже неделю фармлю}. "
    "{Доната жесткого нет|Без доната норм|Донат не нужен}."
)

# ─── Organic responses for real messages ─────────────────────────────────────

ORGANIC_RESPONSES = [
    "Попробуй в поиске телеграма найти Synthesis game bot. Крафт вещей, рецепты — залипательно.",
    "Я ща в Synthesis game bot играю, текстовый крафт. В поиске тг найдешь.",
    "Synthesis game bot норм тема, если любишь крафтить. Через поиск тг ищи.",
    "Мне Synthesis game bot зашел — крафт, лутинг, без доната. Поищи в телеге.",
    "Есть бот Synthesis game bot. Текстовый крафт, рецепты самому открывать интересно.",
]

ORGANIC_SMALLTALK = [
    "Согласен, хорошая тема.",
    "Тоже так думаю.",
    "Интересно, надо глянуть.",
    "Да, есть такое.",
    "Не знал, спасибо.",
    "Прикольно, спасибо за инфу.",
    "+1",
    "На самом деле да, годно.",
]

# ─── Bio texts (spintax) ─────────────────────────────────────────────────────

BIO_SPINTAX = (
    "{Играю|Залип} в {Synthesis_game_bot|Synth game bot}. "
    "{Крафт|Выживание}. {Поиск в тг|Ищи в телеге}."
)

# ─── Keywords to respond to ─────────────────────────────────────────────────

TRIGGER_KEYWORDS = [
    "игр", "поиграть", "посоветуй", "подскажи", "скучно", "залипнуть",
    "текстов", "крафт", "рекоменд", "во что", "через заняться", "free time",
    "bot", "game", "релакс", "расслабить", "убить время",
]

# ─── Helpers ─────────────────────────────────────────────────────────────────

SESSION_CACHE = {}

def load_chats(file_path="chats.txt"):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def get_available_sessions(sessions_dir="./sessions"):
    if not os.path.exists(sessions_dir):
        return []
    sessions = []
    for file in sorted(os.listdir(sessions_dir)):
        if file.endswith(".session"):
            sessions.append(file.replace(".session", ""))
    return sessions

def get_session_name(session_path):
    base = os.path.basename(session_path)
    return base.replace(".session", "")

async def sleep_with_progress(minutes, label, logger, stop_event, interval=5):
    total_seconds = int(minutes * 60)
    remaining_seconds = total_seconds
    while remaining_seconds > 0:
        if stop_event.is_set():
            logger(f"{label} — stopped by user")
            return True
        remaining_minutes = (remaining_seconds + 59) // 60
        if remaining_seconds % (interval * 60) == 0:
            logger(f"{label} — {remaining_minutes} min left")
        await asyncio.sleep(1)
        remaining_seconds -= 1
    return False

async def safe_join(app, name, chat_link, logger):
    try:
        entity = await app.get_entity(chat_link)
        await app(JoinChannelRequest(entity))
        logger(f"[{name}] Joined {chat_link}.")
        return True
    except Exception as e:
        if "already" in str(e).lower():
            logger(f"[{name}] Already in {chat_link}.")
            return True
        if "requested" in str(e).lower():
            logger(f"[{name}] Join requested for {chat_link} (private).")
            return False
        logger(f"[{name}] Join error for {chat_link}: {e}")
        return False

async def init_client_pool(session_names, api_id, api_hash, logger):
    pool = {}
    for name in session_names:
        path = os.path.abspath(f"./sessions/{name}")
        client = TelegramClient(path, api_id, api_hash)
        try:
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                pool[name] = client
                logger(f"✓ {name} — {me.first_name} @{me.username}")
            else:
                logger(f"✗ {name} — not authorized, excluded")
                await client.disconnect()
        except Exception as e:
            logger(f"✗ {name} — {e}")
            try:
                await client.disconnect()
            except:
                pass
    return pool

async def set_bios(client_pool, logger, stop_event):
    logger("=== Checking/setting account bios... ===")
    idx = 0
    for name, client in client_pool.items():
        if stop_event.is_set():
            break
        try:
            me = await client.get_me()
            current_bio = getattr(me, 'about', '') or ''
            desired_bio = render_spintax(BIO_SPINTAX)
            if any(kw in current_bio.lower() for kw in ['synthesis', 'game', 'крафт', 'synth']):
                logger(f"[{name}] Bio already ok, skip")
            else:
                await client(UpdateProfileRequest(about=desired_bio))
                logger(f"[{name}] Bio updated.")
                idx += 1
                if idx % 5 == 0:
                    delay = random.randint(2, 5)
                    logger(f"Bio batch {idx}, waiting {delay} min...")
                    stopped = await sleep_with_progress(delay, "Bio cooldown", logger, stop_event, interval=1)
                    if stopped:
                        break
        except Exception as e:
            logger(f"[{name}] Bio error: {e}")
    logger("=== Bios done ===")

async def close_client_pool(pool):
    for name, client in pool.items():
        try:
            await client.disconnect()
        except:
            pass

def is_message_relevant(text: str) -> bool:
    """Check if a message contains keywords worth responding to."""
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in TRIGGER_KEYWORDS)

def should_ignore_sender(msg, own_usernames: set) -> bool:
    """Skip messages from our own accounts to avoid echo."""
    sender = msg.sender
    if not sender:
        return True
    username = sender.username or ""
    return username.lower() in own_usernames

async def get_own_usernames(client_pool) -> set:
    """Get set of our account usernames to detect self-messages."""
    usernames = set()
    for name, client in client_pool.items():
        try:
            me = await client.get_me()
            if me.username:
                usernames.add(me.username.lower())
        except:
            pass
    return usernames

# ─── Database (claimed chats) ─────────────────────────────────────────────────

DB_PATH = "campaign.db"
_db_lock = threading.Lock()

def init_db():
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS claimed_chats (
                chat_username TEXT UNIQUE NOT NULL,
                claimed_by TEXT NOT NULL,
                claimed_at REAL NOT NULL,
                last_active_at REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_counts (
                session_name TEXT NOT NULL,
                date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (session_name, date)
            )
        """)
        conn.commit()
        conn.close()

def get_account_chats(account_name):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(
            "SELECT chat_username FROM claimed_chats WHERE claimed_by=? AND is_active=1 ORDER BY claimed_at",
            (account_name,)
        )
        result = [row[0] for row in cur.fetchall()]
        conn.close()
        return result

def get_all_claimed():
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT chat_username FROM claimed_chats WHERE is_active=1")
        result = {row[0] for row in cur.fetchall()}
        conn.close()
        return result

def claim_chat(chat_username, account_name):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "INSERT INTO claimed_chats (chat_username, claimed_by, claimed_at) VALUES (?, ?, ?)",
                (chat_username, account_name, time.time())
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

def release_chat(chat_username):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE claimed_chats SET is_active=0 WHERE chat_username=?", (chat_username,))
        conn.commit()
        conn.close()

def update_last_active(chat_username):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE claimed_chats SET last_active_at=? WHERE chat_username=?", (time.time(), chat_username))
        conn.commit()
        conn.close()

def count_account_chats(account_name):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(
            "SELECT COUNT(*) FROM claimed_chats WHERE claimed_by=? AND is_active=1",
            (account_name,)
        )
        count = cur.fetchone()[0]
        conn.close()
        return count

# ─── Daily message limits ─────────────────────────────────────────────────────

DAILY_MESSAGE_LIMIT = 8

def get_daily_count(account_name: str) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(
            "SELECT count FROM daily_counts WHERE session_name=? AND date=?",
            (account_name, today)
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0

def increment_daily_count(account_name: str):
    today = datetime.now().strftime("%Y-%m-%d")
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO daily_counts (session_name, date, count)
            VALUES (?, ?, 1)
            ON CONFLICT(session_name, date) DO UPDATE SET count = count + 1
        """, (account_name, today))
        conn.commit()
        conn.close()

# ─── Human behavior helpers ────────────────────────────────────────────────────

DAILY_MESSAGE_LIMIT = 8  # max messages per account per day

def is_daytime() -> bool:
    """Only active 10:00-23:00 (human awake hours)."""
    h = datetime.now().hour
    return 10 <= h < 23

def human_delay(min_sec: float = 5, max_sec: float = 60) -> float:
    """Normal distribution delay centered at (min+max)/2, clamped."""
    mu = (min_sec + max_sec) * 0.5
    sigma = (max_sec - min_sec) * 0.25
    return max(min_sec, min(max_sec, random.gauss(mu, sigma)))

async def split_and_send(client, entity, text, logger, name, reply_to=None):
    """Split text by newlines, send as multiple messages with human gaps."""
    parts = [p.strip() for p in text.replace('\r\n', '\n').split('\n') if p.strip()]
    if not parts:
        return False
    for i, part in enumerate(parts):
        await client.send_message(entity, part, reply_to=(reply_to if i == 0 else None))
        if i < len(parts) - 1:
            await asyncio.sleep(human_delay(2, 8))
    logger(f"[{name}] Sent {len(parts)} messages")
    return True

async def check_spambot(client, name, logger) -> bool:
    """Check account health via @spambot. Returns False if restricted."""
    try:
        spambot = await client.get_entity('@spambot')
        await client.send_message(spambot, '/start')
        await asyncio.sleep(3)
        msgs = await client.get_messages(spambot, limit=1)
        if msgs and msgs[0] and msgs[0].text:
            txt = msgs[0].text.lower()
            if any(w in txt for w in ['ограничен', 'limited', 'banned', 'забанен', 'спам']):
                logger(f"[{name}] @spambot: ACCOUNT RESTRICTED!")
                return False
        return True
    except Exception as e:
        logger(f"[{name}] @spambot check error: {e}")
        return True  # assume OK on error

# ─── Chat discovery: DuckDuckGo → aggregator sites → SearchGlobalRequest ─────

WEB_SEARCH_KEYWORDS = [
    "telegram game chat",
    "telegram gaming group",
    "telegram games community",
    "telegram game discussion",
    "telegram gamer chat",
    "telegram group game",
    "telegram multiplayer chat",
    "telegram rpg group",
    "telegram игровой чат",
    "telegram игры обсуждение",
    "telegram гейминг",
    "telegram game community join",
    "telegram игровой чат",
    "telegram игры обсуждение",
    "telegram геймеры",
    "telegram майнкрафт",
    "telegram дота",
]

_web_search_offset: int = 0
_aggregator_crawl_offset: int = 0
_web_rate_limiter = asyncio.Lock()
_last_web_request: float = 0

# Aggregator categories on telegram-groups.com
AGGREGATOR_CATEGORIES = ["games", "gaming", "pokemon", "anime"]

SKIP_USERNAMES = {
    "joinchat", "s", "addstickers", "share", "proxy",
    "contact", "invoice", "pay", "k", "i", "bg",
    "me", "t", "x", "telegram", "bot", "bots",
}


def _clean_username(uname: str) -> str | None:
    u = uname.lower().strip()
    if u in SKIP_USERNAMES or len(u) < 4:
        return None
    return f"@{uname}"


async def _check_chat_via_tme_s(link: str, logger) -> bool:
    """Check chat via t.me/s/ page — returns True if likely gaming-themed."""
    skip = ["crypto", "signals", "trading", "forex", "sport", "betting",
            "porn", "adult", "nude", "dating", "news", "music", "movie",
            "nft", "token", "blockchain", "decentrali", "exchange",
            "airdrop", "mining", "whale", "p2p", "defi", "dao",
            "casino", "slot", "poker", "shop", "store", "price",
            "presale", "ido", "launchpad", "staking", "yield", "earn",
            "investment", "profit", "bonus", "referral", "cash",
            "buy", "sell", "market", "coin", "wallet"]
    good = ["game", "gaming", "gamer", "play", "игр", "игра", "discord",
            "community", "chat", "group", "clan", "guild", "mmorpg",
            "rpg", "craft", "survival", "steam", "minecraft",
            "dota", "csgo", "valorant", "pubg", "fortnite",
            "roblox", "gta", " multiplayer", "online", "co-op"]
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
            c.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            r = await c.get(f"https://t.me/s/{link.lstrip('@')}")
            if r.status_code != 200:
                return False  # can't check → skip
            text = r.text.lower()
            for kw in skip:
                if kw in text:
                    return False
            for kw in good:
                if kw in text:
                    return True
            return False  # no gaming keywords found
    except Exception:
        return False


async def _search_via_duckduckgo(exclude_set, logger):
    """Search DuckDuckGo for t.me links with gaming keywords (rate-limited).
    Tries ddgs library first, falls back to raw httpx."""
    global _web_search_offset, _last_web_request

    kw = WEB_SEARCH_KEYWORDS[_web_search_offset % len(WEB_SEARCH_KEYWORDS)]
    _web_search_offset += 1

    async with _web_rate_limiter:
        now = time.time()
        wait = 6.0 - (now - _last_web_request)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_web_request = time.time()

    def _parse_links(results: list) -> list[str]:
        links = []
        for r in results:
            href = r.get('href', '')
            for m in re.finditer(r't\.me/([a-zA-Z0-9_]{3,})', href):
                uname = _clean_username(m.group(1))
                if uname and uname not in exclude_set:
                    links.append(uname)
        return links

    try:
        from duckduckgo_search import DDGS
        results = await asyncio.to_thread(
            lambda: list(DDGS().text(kw, max_results=20, region='ru-ru'))
        )
        if results:
            usernames = _parse_links(results)
            if usernames:
                logger(f"  DuckDuckGo lib found {len(usernames)} for '{kw}'")
                for link in usernames[:5]:
                    if await _check_chat_via_tme_s(link, logger):
                        return link
                return usernames[0]
    except Exception as lib_err:
        logger(f"  DuckDuckGo lib error ({lib_err!r}), trying httpx...")

    # Fallback: raw httpx
    url = f"https://html.duckduckgo.com/html/?q={quote(kw)}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            c.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            })
            r = await c.get(url)
            if r.status_code != 200:
                snippet = r.text[:80].strip().replace('\n', ' ')
                logger(f"  DuckDuckGo httpx {r.status_code} for '{kw}' -> {snippet}")
                return None

            usernames = []
            for m in re.finditer(r'(?:https?://)?t\.me/([a-zA-Z0-9_]{3,})', r.text):
                uname = _clean_username(m.group(1))
                if uname and uname not in exclude_set:
                    usernames.append(uname)

            if usernames:
                logger(f"  DuckDuckGo httpx found {len(usernames)} for '{kw}'")
                for link in usernames[:5]:
                    if await _check_chat_via_tme_s(link, logger):
                        return link
                return usernames[0]
            return None

    except Exception as e:
        logger(f"  DuckDuckGo httpx error: {e!r}")
        return None


async def _crawl_aggregator(exclude_set, logger):
    """Crawl telegram-groups.com listing pages for t.me links (rate-limited).
    Extracts member counts from listing page to pre-filter by size."""
    global _aggregator_crawl_offset, _last_web_request

    cat = AGGREGATOR_CATEGORIES[_aggregator_crawl_offset % len(AGGREGATOR_CATEGORIES)]
    _aggregator_crawl_offset += 1

    async with _web_rate_limiter:
        now = time.time()
        wait = 6.0 - (now - _last_web_request)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_web_request = time.time()

    list_url = f"https://www.telegram-groups.com/{cat}-telegram-groups/"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
            c.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            r = await c.get(list_url)
            if r.status_code != 200:
                return None

            # Extract listing IDs with their member counts from listing page HTML
            listings_subs = {}
            for m in re.finditer(r'/([\w-]+)/listing/([a-f0-9]+)/', r.text):
                cat2, lid = m.group(1), m.group(2)
                start = max(0, m.start() - 150)
                end = min(len(r.text), m.end() + 250)
                context = r.text[start:end]
                mem = re.search(r'👥\s*([\d,]+)', context)
                subs = int(mem.group(1).replace(',','')) if mem else 0
                if lid not in listings_subs or subs > listings_subs[lid][1]:
                    listings_subs[lid] = (cat2, subs)

            # Sort by subscriber count descending, filter 50+
            ranked = [(lid, cat2, subs) for lid, (cat2, subs) in listings_subs.items() if subs >= 50]
            ranked.sort(key=lambda x: -x[2])
            if not ranked:
                logger(f"  Aggregator {cat}: no listings with 50+ members")
                return None

            logger(f"  Aggregator {cat}: {len(ranked)} listings with 50+ subs, best={ranked[0][2]:,}")
            for lid, cat2, subs in ranked[:15]:
                detail_url = f"https://www.telegram-groups.com/{cat2}/listing/{lid}/"
                try:
                    r2 = await c.get(detail_url)
                    if r2.status_code != 200:
                        continue
                    for m in re.finditer(r't\.me/([a-zA-Z0-9_]{3,})', r2.text):
                        uname = _clean_username(m.group(1))
                        if uname and uname not in exclude_set:
                            logger(f"  Aggregator found {uname} ({cat}, {subs:,} subs)")
                            if await _check_chat_via_tme_s(uname, logger):
                                return uname
                            return uname
                except Exception:
                    continue
            return None

    except Exception as e:
        logger(f"  Aggregator crawl error: {e}")
        return None


async def _search_telegram_global(client, exclude_set, logger):
    """Search Telegram via SearchGlobalRequest with groups_only=True.
    Uses `result.chats` directly to avoid redundant get_entity calls."""
    keywords = [
        # English gaming
        "games", "gaming", "game", "mmorpg", "rpg", "craft",
        "survival", "steam", "minecraft", "gta", "pubg",
        "mobile games", "game discussion",
        "mmo", "clan", "guild", "online games",
        "gamer chat", "gaming community", "game lovers",
        "multiplayer", "coop games", "sandbox",
        "indie games", "game dev", "game design",
        # Popular games
        "dota 2", "csgo", "cs2", "valorant", "fortnite",
        "roblox", "terraria", "stardew valley", "factorio",
        "rust", "dayz", "arksurvival", "warcraft",
        "world of warcraft", "wow", "league of legends",
        "overwatch", "apex legends", "team fortress",
        "euro truck", "simulator", "hearts of iron",
        # Russian gaming
        "игры", "гейминг", "игровой чат", "игровое сообщество",
        "online игры", "компьютерные игры",
        "видеоигры", "обсуждение игр", "геймеры",
        "игровой сервер", "кланы", "гильдия",
        "сервер майнкрафт", "майнкрафт чат",
        "дота 2", "кс го", "кс2", "каэска",
        "варфейс", "world of tanks", "wot",
        "танки онлайн", "world of warships",
        "steam игры", "пиратка", "торренты игр",
        # Game genres in Russian
        "ролевые игры", "стратегии", "шутеры",
        "выживание", "песочница", "хоррор игры",
        "гонки", "симуляторы", "ферма",
        "пошаговые стратегии", "градостроительные симуляторы",
        # Communities
        "game night", "game party", "игровая ночь",
        "team up", "поиск команды", "поиск сокомандников",
        "своя игра", "настольные игры online",
        "discord сервер", "discord игры",
        # RPG specific
        "dungeons", "dragons", "fantasy rpg",
        "text rpg", "текстовый квест", "text quest",
        "mmo rpg", "браузерные игры", "online rpg",
        # Tech gaming
        "game optimization", "настройка игр",
        "игровой компьютер", "сборка пк",
        "fps", "benchmark", "игровая производительность",
    ]
    random.shuffle(keywords)
    for kw in keywords:
        try:
            result = await client(SearchGlobalRequest(
                q=kw,
                filter=InputMessagesFilterEmpty(),
                groups_only=True,
                offset_rate=0,
                offset_peer=InputPeerEmpty(),
                offset_id=0,
                limit=100,
                min_date=0,
                max_date=0,
            ))
            # Collect unique usernames from result.chats
            seen = set()
            candidates = []
            chats = getattr(result, 'chats', [])
            if not chats and hasattr(result, 'messages'):
                # Extract from messages if chats is missing
                for msg in result.messages[:30]:
                    try:
                        entity = await client.get_entity(msg.peer_id)
                        if entity: chats.append(entity)
                    except Exception:
                        continue

            for chat in chats:
                username = getattr(chat, 'username', None)
                if not username:
                    continue
                # Skip broadcast channels (news, announcements, etc.)
                if getattr(chat, 'broadcast', False):
                    continue
                # Prefer megagroups (true groups) over non-megagroup channels
                is_group = getattr(chat, 'megagroup', False)
                link = f"@{username}"
                if link in exclude_set or link in seen:
                    continue
                seen.add(link)
                candidates.append((link, is_group))

            if candidates:
                # Sort: groups first, then channels
                candidates.sort(key=lambda x: -x[1])
                result = candidates[0][0]
                logger(f"  TG Global: {result} ({'group' if candidates[0][1] else 'channel'})")
                if len(candidates) > 1:
                    extra = ', '.join(c[0] for c in candidates[1:6])
                    logger(f"    also: {extra}")
                return result

            await asyncio.sleep(0.5)
        except FloodWaitError as e:
            if e.seconds < 600:
                logger(f"  Flood wait {e.seconds}s, waiting...")
                await asyncio.sleep(e.seconds + 5)
            else:
                return None
        except Exception as e:
            logger(f"  TG global search error for '{kw}': {e}")
            continue
    return None


async def _check_subs_logged(client, link: str, logger) -> bool:
    """Check subs, log result. Skip broadcast channels and users."""
    try:
        entity = await client.get_entity(link)
        subs = getattr(entity, "participants_count", 0) or 0
        etype = type(entity).__name__

        # Skip broadcast channels (non-megagroup channels)
        if hasattr(entity, 'broadcast') and entity.broadcast:
            logger(f"  {link} — {etype}, subs={subs}, SKIP (broadcast channel)")
            return False

        # Skip users (not chats)
        if hasattr(entity, 'bot') or (hasattr(entity, 'photo') and not hasattr(entity, 'participants_count')):
            logger(f"  {link} — {etype}, SKIP (user, not a chat)")
            return False

        logger(f"  {link} — {etype}, subs={subs}")
        if subs >= 20:
            return True
        logger(f"  {link} — too small ({subs} subs) or no participant count")
        return True  # try anyway — 0 may mean no access
    except Exception as e:
        logger(f"  {link} — entity error: {e}")
        return True  # try anyway on error


async def _search_via_searchee_bot(client, exclude_set, logger):
    """Search chats via @SearcheeBot inline query (backed by TGStat data).
    Returns first valid t.me link not in exclude_set."""
    queries = [
        "игры", "гейминг", "майнкрафт", "дота", "mmorpg",
        "game", "gaming", "rpg", "survival", "craft",
        "игровой чат", "игровое сообщество", "steam", "minecraft",
        "online игры", "геймеры", "discord", "pubg", "cs", "gta",
    ]
    kw = random.choice(queries)
    try:
        results = await client.inline_query("@SearcheeBot", kw)
        usernames = []
        for r in results:
            desc = r.description or ''
            m = re.match(r'@([a-zA-Z0-9_]{3,})', desc.strip())
            if m:
                uname = _clean_username(m.group(1))
                if uname and uname not in exclude_set:
                    usernames.append(uname)
                    if len(usernames) >= 3:
                        break
        if usernames:
            logger(f"  SearcheeBot found {len(usernames)} for '{kw}'")
            return usernames[0]
        logger(f"  SearcheeBot: no results for '{kw}'")
        return None
    except Exception as e:
        logger(f"  SearcheeBot error: {e}")
        return None


async def discover_new_chat(client, exclude_set, logger):
    """Search for a Telegram chat with 50+ subs, not in exclude_set.
    Phase 1: SearcheeBot inline query (TGStat, real group data).
    Phase 2: SearchGlobalRequest with groups_only=True (native Telegram search).
    Phase 3: telegram-groups.com aggregator crawl (with 50+ member filter).
    Phase 4: DuckDuckGo web search (last resort)."""
    logger("  Phase 1: SearcheeBot (TGStat)...")
    link = await _search_via_searchee_bot(client, exclude_set, logger)
    if link and await _check_subs_logged(client, link, logger):
        return link
    elif link:
        logger(f"  Phase 1 failed for {link}")

    logger("  Phase 2: Telegram global search (groups only)...")
    link = await _search_telegram_global(client, exclude_set, logger)
    if link and await _check_subs_logged(client, link, logger):
        return link
    elif link:
        logger(f"  Phase 2 failed for {link}")

    logger("  Phase 3: Aggregator sites...")
    link = await _crawl_aggregator(exclude_set, logger)
    if link and await _check_subs_logged(client, link, logger):
        return link
    elif link:
        logger(f"  Phase 3 failed for {link}")

    logger("  Phase 4: DuckDuckGo...")
    link = await _search_via_duckduckgo(exclude_set, logger)
    if link and await _check_subs_logged(client, link, logger):
        return link
    return None

# ─── Phase 1: JOIN (with staggered start) ────────────────────────────────────

async def join_account_chats(acc_name, chat_list, api_id, api_hash, join_map, logger, stop_event):
    session_path = os.path.abspath(f"./sessions/{acc_name}")
    client = TelegramClient(session_path, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger(f"[{acc_name}] NOT AUTHORIZED, skipping joins")
            return
        for batch_num, chat in enumerate(chat_list):
            if stop_event.is_set():
                break
            ok = await safe_join(client, acc_name, chat, logger)
            if ok:
                join_map[chat] = acc_name
                with open(JOIN_MAP_FILE, "w", encoding="utf-8") as f:
                    json.dump(join_map, f, ensure_ascii=False, indent=2)
            delay = random.randint(10, 20)
            logger(f"[{acc_name}] Next join in {delay} min...")
            stopped = await sleep_with_progress(delay, f"[{acc_name}] Join cooldown", logger, stop_event, interval=5)
            if stopped:
                break
            if (batch_num + 1) % 5 == 0:
                break_hours = random.randint(2, 4)
                logger(f"[{acc_name}] {batch_num+1} joins done. Break {break_hours}h...")
                stopped = await sleep_with_progress(break_hours * 60, f"[{acc_name}] Long break", logger, stop_event, interval=30)
                if stopped:
                    break
    finally:
        await client.disconnect()

async def phase_join(chats, authorized, api_id, api_hash, logger, stop_event):
    join_map = {}
    total = len(chats)
    acc_count = len(authorized)

    logger(f"=== Phase 1: JOIN. {total} chats, {acc_count} accounts ===")

    acc_chats = {acc: [] for acc in authorized}
    for idx, chat in enumerate(chats):
        acc = authorized[idx % acc_count]
        acc_chats[acc].append(chat)

    for acc, chat_list in acc_chats.items():
        logger(f"  {acc}: {len(chat_list)} chats")

    # Staggered start: launch tasks with delays between them
    tasks = []
    for acc, chat_list in acc_chats.items():
        if not chat_list:
            continue
        task = asyncio.create_task(join_account_chats(acc, chat_list, api_id, api_hash, join_map, logger, stop_event))
        tasks.append(task)
        stagger_minutes = random.randint(3, 10)
        logger(f"  Stagger: next account starts in {stagger_minutes} min")
        stopped = await sleep_with_progress(stagger_minutes, "Stagger delay", logger, stop_event, interval=1)
        if stopped:
            break

    await asyncio.gather(*tasks, return_exceptions=True)

    logger(f"=== Phase 1 done: {len(join_map)} chats joined ===")
    return join_map

# ─── Phase 2: CHAT (organic participation + on-the-fly discovery) ──────────────

async def phase_chat(client_pool, logger, stop_event):
    """
    Each account independently maintains up to 10 chat slots.
    - Polls existing chats for relevant messages → responds organically
    - If a slot is empty or the chat is dead → discovers a new chat via SearchGlobalRequest
    - Claims the chat in SQLite DB (no duplicates across accounts)
    """
    own_usernames = await get_own_usernames(client_pool)
    init_db()
    max_slots = 10

    logger(f"=== CHAT mode: {len(client_pool)} accounts, {max_slots} slots each ===")

    last_action: dict = {}
    last_chat_action: dict = {}
    last_poll: dict = {}
    poll_errors: dict = {}  # track consecutive poll failures per chat

    def is_write_error(e: Exception) -> bool:
        err = str(e).lower()
        return any(x in err for x in [
            "you can't write", "no write permission", "premium required",
            "payment_required", "broadcast", "channel", "user is restricted",
            "chat write forbidden", "not enough rights",
        ])

    async def ensure_subscribed(entity, name, client):
        """If entity has a linked channel, join it (required for write in many groups)."""
        try:
            linked_id = getattr(entity, 'linked_chat_id', None)
            if linked_id:
                try:
                    linked = await client.get_entity(linked_id)
                    if hasattr(linked, 'username') and linked.username:
                        from telethon.tl.functions.channels import JoinChannelRequest
                        await client(JoinChannelRequest(linked))
                        logger(f"[{name}] Joined linked channel @{linked.username}")
                except Exception as e:
                    if "already" in str(e).lower():
                        pass  # already joined, fine
                    else:
                        logger(f"[{name}] Linked channel join: {e}")
        except Exception:
            pass

    async def try_intro(chat_link, name, client, own_usernames_set):
        """Send first message in a newly claimed chat. Uses Gemini for context, fallback to template."""
        try:
            entity = await client.get_entity(chat_link)
            if hasattr(entity, 'broadcast') and entity.broadcast:
                logger(f"[{name}] {chat_link} is broadcast, releasing")
                return False
            await ensure_subscribed(entity, name, client)
            recent = await client.get_messages(entity, limit=5)
            target_msg = next((m for m in recent if m and m.text and not m.out and not should_ignore_sender(m, own_usernames_set)), None)
            await asyncio.sleep(random.randint(15, 45))
            if target_msg:
                context_lines = []
                for m in recent[:5]:
                    if m and m.text:
                        if m.out:
                            context_lines.append(f"я: {m.text}")
                        elif not should_ignore_sender(m, own_usernames_set):
                            nt = getattr(m.sender, 'first_name', 'пользователь') or 'пользователь'
                            context_lines.append(f"{nt}: {m.text}")
                ctx = "\n".join(context_lines)
                reply = await generate_gemini_response(ctx)
                if not reply:
                    reply = random.choice(ORGANIC_RESPONSES)
                await client.send_message(entity, reply, reply_to=target_msg)
                logger(f"[{name}] Gemini intro in {chat_link}")
            else:
                intro = f"Кто играл в {random.choice(['Synthesis game bot', 'Synth game бот', 'Synthesis game'])}, норм крафт?"
                await client.send_message(entity, intro)
                logger(f"[{name}] Intro question in {chat_link}")
            update_last_active(chat_link)
            return True
        except Exception as e:
            if is_write_error(e):
                logger(f"[{name}] Can't write in {chat_link}: {e}")
                return False
            logger(f"[{name}] Intro error in {chat_link}: {e}")
            return True

    async def account_loop(name, client, discovery_semaphore):
        logger(f"[{name}] Starting...")
        cycle_count = 0
        while not stop_event.is_set():
            cycle_count += 1

            # ── 0. Night mode: sleep until morning ──────────────────────────
            while not is_daytime() and not stop_event.is_set():
                logger(f"[{name}] Night time, sleeping 30 min...")
                for _ in range(1800):
                    if stop_event.is_set() or is_daytime():
                        break
                    await asyncio.sleep(1)

            # ── 1. Long break every 5 cycles ────────────────────────────────
            if cycle_count > 1 and cycle_count % 5 == 0:
                break_hours = random.uniform(1.5, 3)
                logger(f"[{name}] Long break {break_hours:.1f}h (cycle {cycle_count})...")
                for _ in range(int(break_hours * 3600)):
                    if stop_event.is_set():
                        return
                    await asyncio.sleep(1)

            # ── 2. Daily limit check ────────────────────────────────────────
            daily = get_daily_count(name)
            if daily >= DAILY_MESSAGE_LIMIT:
                logger(f"[{name}] Daily limit {DAILY_MESSAGE_LIMIT} reached, skipping cycle")
                for _ in range(3600):
                    if stop_event.is_set():
                        return
                    await asyncio.sleep(1)
                continue

            # ── 3. 25% chance to skip (human is busy) ───────────────────────
            if random.random() < 0.25:
                logger(f"[{name}] Skipping cycle (human break)")
                for _ in range(random.randint(300, 600)):
                    if stop_event.is_set():
                        return
                    await asyncio.sleep(1)
                continue

            # ── 4. @spambot check every 10 cycles ───────────────────────────
            if cycle_count % 10 == 0:
                ok = await check_spambot(client, name, logger)
                if not ok:
                    logger(f"[{name}] Account restricted! Sleeping 2h...")
                    for _ in range(7200):
                        if stop_event.is_set():
                            return
                        await asyncio.sleep(1)
                    continue

            my_chats = get_account_chats(name)

            # ── Phase A: Fill empty slots via discovery ────────────────────
            if len(my_chats) < max_slots:
                needed = max_slots - len(my_chats)
                logger(f"[{name}] {len(my_chats)}/{max_slots} slots, discovering {needed}...")
                exclude = get_all_claimed()
                for _ in range(needed):
                    if stop_event.is_set():
                        return
                    async with discovery_semaphore:
                        new_chat = await discover_new_chat(client, exclude, logger)
                    if not new_chat:
                        logger(f"[{name}] No more chats found this cycle")
                        break
                    ok = claim_chat(new_chat, name)
                    if not ok:
                        continue
                    exclude.add(new_chat)
                    my_chats.append(new_chat)
                    await safe_join(client, name, new_chat, logger)
                    await asyncio.sleep(human_delay(20, 60))
                    intro_ok = await try_intro(new_chat, name, client, own_usernames)
                    if not intro_ok:
                        logger(f"[{name}] Releasing {new_chat} (can't write)")
                        release_chat(new_chat)
                        my_chats = get_account_chats(name)
                        await asyncio.sleep(human_delay(30, 90))
                        continue
                    increment_daily_count(name)
                    await asyncio.sleep(human_delay(120, 300))

            # ── Phase B: Poll existing chats for organic replies ───────────
            my_chats = get_account_chats(name)
            random.shuffle(my_chats)
            for chat_link in my_chats:
                if stop_event.is_set():
                    return

                now = time.time()
                if now - last_poll.get(chat_link, 0) < random.randint(300, 480):
                    continue
                last_poll[chat_link] = now

                try:
                    entity = await client.get_entity(chat_link)
                    messages = await client.get_messages(entity, limit=10)
                except Exception as e:
                    logger(f"[{name}] Poll error {chat_link}: {e}")
                    poll_errors[chat_link] = poll_errors.get(chat_link, 0) + 1
                    if poll_errors[chat_link] >= 3:
                        logger(f"[{name}] Releasing {chat_link} (3+ poll errors)")
                        release_chat(chat_link)
                    continue

                poll_errors[chat_link] = 0

                target_msg = None
                for msg in messages:
                    if not msg or not msg.text:
                        continue
                    if msg.out:
                        continue
                    if should_ignore_sender(msg, own_usernames):
                        continue
                    if is_message_relevant(msg.text):
                        target_msg = msg
                        break

                if target_msg:
                    if now - last_action.get(name, 0) < 300:
                        continue
                    if now - last_chat_action.get(entity.id, 0) < 1800:
                        continue
                    if random.random() > 0.4:
                        continue

                    last_action[name] = now
                    last_chat_action[entity.id] = now
                    update_last_active(chat_link)
                    increment_daily_count(name)

                    context_lines = []
                    for m in messages[:5]:
                        if m and m.text:
                            if m.out:
                                context_lines.append(f"я: {m.text}")
                            elif not should_ignore_sender(m, own_usernames):
                                name_tag = getattr(m.sender, 'first_name', 'пользователь') or 'пользователь'
                                context_lines.append(f"{name_tag}: {m.text}")
                    context_text = "\n".join(context_lines)

                    await asyncio.sleep(human_delay(5, 25))
                    await ensure_subscribed(entity, name, client)
                    try:
                        response = await generate_gemini_response(context_text)
                        if not response:
                            response = random.choice(ORGANIC_RESPONSES)
                        ok = await split_and_send(client, entity, response, logger, name, reply_to=target_msg)
                        if not ok:
                            await client.send_message(entity, response, reply_to=target_msg)
                        logger(f"[{name}] Replied in {chat_link}")
                    except Exception as e:
                        logger(f"[{name}] Reply error: {e}")
                        if is_write_error(e):
                            logger(f"[{name}] Releasing {chat_link} (write blocked)")
                            release_chat(chat_link)

            # ── Phase C: Gemini natural reply (3% per cycle) ──────────────────
            my_chats = get_account_chats(name)
            if my_chats and not stop_event.is_set() and random.random() < 0.03:
                target = random.choice(my_chats)
                try:
                    entity = await client.get_entity(target)
                    if hasattr(entity, 'broadcast') and entity.broadcast:
                        continue
                    recent = await client.get_messages(entity, limit=5)
                    last_msg = next((m for m in recent if m and m.text and not m.out and not should_ignore_sender(m, own_usernames)), None)
                    if not last_msg:
                        continue
                    spammy = ["заработк", "доход", "инвестици", "пассивн", "дополнительн", "финанс", "деньги", "заработок", "work", "earn", "money"]
                    if any(s in last_msg.text.lower() for s in spammy):
                        continue
                    context_lines = []
                    for m in recent[:5]:
                        if m and m.text:
                            if m.out:
                                context_lines.append(f"я: {m.text}")
                            elif not should_ignore_sender(m, own_usernames):
                                name_tag = getattr(m.sender, 'first_name', 'пользователь') or 'пользователь'
                                context_lines.append(f"{name_tag}: {m.text}")
                    ctx = "\n".join(context_lines)
                    await asyncio.sleep(human_delay(10, 60))
                    await ensure_subscribed(entity, name, client)
                    reply = await generate_gemini_response(ctx)
                    if not reply:
                        reply = random.choice(ORGANIC_SMALLTALK)
                    increment_daily_count(name)
                    await client.send_message(entity, reply, reply_to=last_msg)
                    logger(f"[{name}] Gemini reply in {target}")
                except Exception:
                    pass

            # ── Wait before next cycle ──────────────────────────────────────
            wait = random.randint(300, 480)
            for _ in range(wait):
                if stop_event.is_set():
                    return
                await asyncio.sleep(1)

    discovery_semaphore = asyncio.Semaphore(2)

    async def account_loop_wrapper(name, client):
        # Stagger at start — each account begins 60-180s apart
        await asyncio.sleep(random.randint(60, 180))
        await account_loop(name, client, discovery_semaphore)

    tasks = [asyncio.create_task(account_loop_wrapper(name, client)) for name, client in client_pool.items()]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger("=== CHAT mode done ===")

# ─── Fallback: Legacy dialogue mode (with spintax + survival validation) ─────

async def run_dialogue_with_clients(client_a, name_a, client_b, name_b, chat_link, logger, stop_event):
    """Legacy Q&A dialogue between two controlled accounts."""
    question_text = render_spintax(QUESTION_SPINTAX)
    answer_text = render_spintax(ANSWER_SPINTAX)

    try:
        entity = await client_a.get_entity(chat_link)
        can_write = await check_can_write(client_a, chat_link, name_a, logger)
        if not can_write:
            return
        can_write = await check_can_write(client_b, chat_link, name_b, logger)
        if not can_write:
            return

        logger(f"--- Scene in {chat_link} | Actors: {name_a} & {name_b} ---")

        lurk_a = random.randint(15, 30)
        stopped = await sleep_with_progress(lurk_a, f"[{name_a}] Lurking before post", logger, stop_event)
        if stopped:
            return

        msg_a = await client_a.send_message(entity, question_text)
        logger(f"[{name_a}] Question posted.")

        delay = random.randint(15, 25)
        stopped = await sleep_with_progress(delay, f"[{name_b}] Waiting to reply", logger, stop_event)
        if stopped:
            return

        # Survival validation: check if question still exists
        try:
            msgs = await client_b.get_messages(entity, ids=msg_a.id)
            survived = msgs and len(msgs) > 0 and msgs[0] is not None
        except Exception:
            survived = False

        if not survived:
            logger(f"[{name_b}] Question was deleted (moderated). Skipping answer in {chat_link}")
            return

        await asyncio.sleep(random.randint(2, 5))
        await client_b.send_message(entity, answer_text, reply_to=msg_a)
        logger(f"[{name_b}] Reply posted.")

    except RPCError as e:
        err = str(e)
        if "PAYMENT_REQUIRED" in err:
            logger(f"[{chat_link}] Premium required, skipping.")
        elif "You can't write" in err:
            logger(f"[{chat_link}] No write permission, skipping.")
        elif "join the discussion group" in err:
            logger(f"[{chat_link}] Linked discussion group, skipping.")
        else:
            logger(f"Error in {chat_link}: {e}")
    except Exception as e:
        logger(f"Error in {chat_link}: {e}")

async def check_can_write(client, chat_link, name, logger):
    try:
        entity = await client.get_entity(chat_link)
        if hasattr(entity, 'broadcast') and entity.broadcast:
            logger(f"[{name}] {chat_link} is a channel, skipping")
            return False
        return True
    except Exception as e:
        logger(f"[{name}] Check error for {chat_link}: {e}")
        return False

async def phase_dialogue(join_map, client_pool, logger, stop_event):
    """Legacy dialogue mode (fallback)."""
    chat_accounts = list(join_map.items())
    total = len(chat_accounts)
    acc_names = list(client_pool.keys())

    logger(f"=== Phase 2: DIALOGUES (legacy mode). {total} chats ===")

    chat_index = 0
    while chat_index < total:
        if stop_event.is_set():
            break

        batch = []
        used_accounts = set()

        for chat, acc_name in chat_accounts[chat_index:]:
            if len(batch) >= len(acc_names) // 2:
                break
            if acc_name not in client_pool or acc_name in used_accounts:
                continue
            others = [a for a in acc_names if a != acc_name and a not in used_accounts and a in client_pool]
            if not others:
                continue
            other = random.choice(others)
            used_accounts.add(acc_name)
            used_accounts.add(other)
            batch.append((chat, client_pool[acc_name], acc_name, client_pool[other], other))
            chat_index += 1

        if not batch:
            logger("No more valid pairs found.")
            break

        logger(f"--- Running {len(batch)} dialogues sequentially with stagger ---")
        for chat, cl_a, name_a, cl_b, name_b in batch:
            if stop_event.is_set():
                break
            asyncio.create_task(run_dialogue_with_clients(cl_a, name_a, cl_b, name_b, chat, logger, stop_event))
            stagger = random.randint(30, 90)
            for _ in range(stagger):
                if stop_event.is_set():
                    break
                await asyncio.sleep(1)

        if stop_event.is_set() or chat_index >= total:
            break

        cooldown = random.randint(15, 25)
        await sleep_with_progress(cooldown, "Batch cooldown", logger, stop_event, interval=5)

# ─── Main ────────────────────────────────────────────────────────────────────

async def run_campaign(api_id, api_hash, logger, stop_event, mode="chat"):
    try:
        await _run_campaign(api_id, api_hash, logger, stop_event, mode)
    except Exception as e:
        import traceback
        logger(f"FATAL: {e}")
        for line in traceback.format_exc().splitlines():
            logger(line)

async def _run_campaign(api_id, api_hash, logger, stop_event, mode="chat"):
    """
    Run campaign.
    mode="chat" (default): on-the-fly discovery + organic replies, 10 slots per account.
    mode="dialogue": legacy Q&A scripted dialogues (requires chats.txt + join phase).
    """
    all_sessions = get_available_sessions()
    logger(f"Initializing {len(all_sessions)} clients...")
    client_pool = await init_client_pool(all_sessions, api_id, api_hash, logger)

    if len(client_pool) < 2:
        logger("Error: Need at least 2 authorized sessions.")
        await close_client_pool(client_pool)
        return

    if mode == "dialogue":
        # Legacy dialogue mode: requires chats.txt + join phase
        chats = load_chats()
        if not chats:
            logger("Dialogue mode requires chats.txt with chat list.")
            await close_client_pool(client_pool)
            return

        authorized = list(client_pool.keys())
        await close_client_pool(client_pool)
        client_pool = {}

        join_map = await phase_join(chats, authorized, api_id, api_hash, logger, stop_event)
        if stop_event.is_set():
            return

        logger("=== Phase 1 complete. Waiting 24 hours before Phase 2... ===")
        stopped = await sleep_with_progress(1440, "24h wait", logger, stop_event, interval=60)
        if stopped:
            return

        logger("Re-initializing client pool for Phase 2...")
        client_pool = await init_client_pool(authorized, api_id, api_hash, logger)
        if len(client_pool) < 2:
            logger("Error: Not enough valid sessions after wait.")
            await close_client_pool(client_pool)
            return

        await phase_dialogue(join_map, client_pool, logger, stop_event)
    else:
        # Chat mode: integrated discovery, no pre-loaded chats needed
        await phase_chat(client_pool, logger, stop_event)

    await close_client_pool(client_pool)
    logger("=== Campaign finished ===")

```

--- run_campaign.py ---
```python
import asyncio
import os
import sys
import argparse
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))
from promo_engine import run_campaign

API_ID = 19839869
API_HASH = "7963a733802269d97dcb2234604f5801"

def logger(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode('utf-8'), flush=True)

async def main():
    parser = argparse.ArgumentParser(description="Synthesis Promo Campaign")
    parser.add_argument("--mode", choices=["chat", "dialogue"], default="chat",
                        help="chat: respond to real messages (default), dialogue: scripted Q&A")
    args = parser.parse_args()

    stop_event = asyncio.Event()
    logger(f"Starting campaign in '{args.mode}' mode...")
    await run_campaign(API_ID, API_HASH, logger, stop_event, mode=args.mode)

if __name__ == "__main__":
    asyncio.run(main())

```

--- run_chat.bat ---
```python
@echo off
chcp 65001 >nul
python -u run_campaign.py --mode chat
pause

```

--- scenarios.py ---
```python
SCENARIOS = [
    {
        "q": "Блин, скукота. Посоветуйте какую-нибудь залипалку текстовую в телеге, только чтоб без доната жесткого.",
        "a": "Попробуй @Synthesis_game_bot, там механика крафта прикольная, сижу второй день собираю предметы."
    },
    {
        "q": "Народ, кто играл во что-то текстовое в телеге? Что посоветуете?",
        "a": "Я в @Synthesis_game_bot залип, норм тема — рецепты крафта, PvP, кланы. Без доната вполне кайфово."
    },
    {
        "q": "Посоветуйте игру в телеграме чтоб прям затягивало. Желательно без агрессивной монетизации.",
        "a": "@Synthesis_game_bot норм вариант — там крафт, экономика, ивенты. Уже неделю играю, донат не требуется."
    },
    {
        "q": "Есть что-то толковое среди телеграм-игр? Надоели кликеры и дрочильни.",
        "a": "Зацени @Synthesis_game_bot — полноценный RPG крафт с рынком и PvP. Очень годно сделан."
    },
    {
        "q": "Ребята, кто шарит, подскажите текстовую RPG с прокачкой и ремеслом.",
        "a": "@Synthesis_game_bot — то что надо: куча рецептов, аукцион, замес с другими игроками. Сам втыкаю уже месяц."
    },
    {
        "q": "Чем заняться в телеграме пока стоишь в пробке? Игра нужна. 🙃",
        "a": "@Synthesis_game_bot спасает в очередях. Пошаговая RPG, можно фармить ресурсы и ковырять крафт минутами."
    },
    {
        "q": "Может кто подскажет игру где можно прям погрузиться с головой, а не на 5 минут?",
        "a": "Я на @Synthesis_game_bot подсел — там механика глубокая: алхимия, улучшение шмота, замес за ресурсы. Топ."
    },
    {
        "q": "Ищу игру в телеге чтобы было интересно и без доната. Есть варианты?",
        "a": "@Synthesis_game_bot — крафтовая RPG, донат только для ускорения, но без него норм качаться."
    },
    {
        "q": "Кто что думает про телеграм-игры? Есть ли среди них годнота?",
        "a": "Я только @Synthesis_game_bot нашел адекватную. Остальное либо кликеры либо донатные помойки."
    },
    {
        "q": "Посоветуйте что-то в телеге чтоб вайбово и с душой сделано.",
        "a": "@Synthesis_game_bot — пиксельная RPG, ретро стиль, механика интересная. Разработчики живые, слушают комьюнити."
    },
    {
        "q": "Народ, подскажите текстовую RPG в телеграме. Чтоб можно было играть с телефона и компа.",
        "a": "@Synthesis_game_bot кросс-платформенная — запускается в телеграме с любого устройства. Я с телефона фармлю, с компа в PvP захожу."
    },
    {
        "q": "Есть ли в телеграме что-то похожее на старые браузерки? Прям чтоб с крафтом и прокачкой.",
        "a": "@Synthesis_game_bot 100% такое. Крафтишь шмот, торгуешь на рынке, водишь клан. Ностальгия по старым браузеркам."
    },
    {
        "q": "Сижу дома больной, посоветуйте во что убить время в телеге.",
        "a": "Поправляйся! Я ща в @Synthesis_game_bot играю — хорошо отвлекает. Собирание ресурсов и крафт, мозг отдыхает."
    },
    {
        "q": "Кто знает норм телеграм-игры с активным комьюнити и ивентами?",
        "a": "@Synthesis_game_bot — там постоянно ивенты, ивент-боссы, соревнования кланов. Комьюнити живое, народу много."
    },
    {
        "q": "Посоветуйте игру в телеграме для вечера. Чтоб не зашкварно и интересно.",
        "a": "Я залип в @Synthesis_game_bot — вечером заходишь, рецепты крафтишь, с кланом общаешься. Очень расслабляет."
    },
    {
        "q": "Чем сейчас народ в телеге играет? Что в тренде?",
        "a": "Из игр — @Synthesis_game_bot сейчас хайпует, крафтовая RPG с экономикой. Друзья подсадили, сам уже не вылезаю."
    },
]

```

--- test_discovery_one.py ---
```python
"""Full campaign test on one account — discovery, join, send."""
import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\555\tgacc\synthesis_promo_tool')

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from promo_engine import discover_new_chat, safe_join
from datetime import datetime, timezone

API_ID = 19839869
API_HASH = "7963a733802269d97dcb2234604f5801"
SESSION = r"C:\555\tgacc\synthesis_promo_tool\sessions\15"

GEMINI_ENDPOINT = "http://localhost:8081/v1/chat/completions"

skip_due_to_send = set()

def logger(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode('utf-8', errors='replace'), flush=True)

async def gemini_intro(chat_title: str, chat_uname: str) -> str:
    """Generate a short Russian intro for the chat via Gemini proxy."""
    import httpx
    prompt = (
        f"Мы только что зашли в чат \"{chat_title}\" (@{chat_uname}). "
        "Напиши короткое приветственное сообщение (1-3 предложения), в котором "
        "ты представляешься как новый участник, интересуешься что тут обсуждают. "
        "Напиши на русском, без эмодзи, без форматирования. Не рекламируй ничего."
    )
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(GEMINI_ENDPOINT, json={
                "model": "gemini-3.5-flash",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 150,
            })
            if r.status_code == 200:
                msg = r.json()["choices"][0]["message"]["content"].strip()
                return msg
            logger(f"  Gemini error {r.status_code}: {r.text[:100]}")
            return None
    except Exception as e:
        logger(f"  Gemini exception: {e}")
        return None

async def run_one():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    logger(f"Logged in as @{me.username} ({me.first_name})")

    # Phase 1: discover
    exclude = set()
    link = await discover_new_chat(client, exclude, logger)
    if not link:
        logger("No chat found, exiting.")
        await client.disconnect()
        return
    logger(f"\n=== DISCOVERED: {link} ===")

    # Phase 2: join
    ok = await safe_join(client, me.first_name or me.username or "?", link, logger)
    if not ok:
        logger("Could not join, exiting.")
        await client.disconnect()
        return

    # Phase 3: read recent messages
    try:
        entity = await client.get_entity(link)
        title = getattr(entity, 'title', link)
        logger(f"\nChat: {title} (@{entity.username if hasattr(entity,'username') else '?'})")
        logger(f"Type: {type(entity).__name__}, Broadcast={getattr(entity,'broadcast','?')}")

        # Get recent messages
        msgs = await client.get_messages(entity, limit=5)
        logger(f"\n--- Last 5 messages ---")
        for m in reversed(msgs):
            sender = m.sender_id
            text = (m.text or "[non-text]")[:100]
            logger(f"  [{m.id}] {text}")
    except Exception as e:
        logger(f"Error reading messages: {e}")

    # Phase 4: generate and send message
    logger("\n=== Generating message via Gemini ===")
    msg = await gemini_intro(title, entity.username if hasattr(entity, 'username') else '?')
    if msg:
        logger(f"\nGemini response:\n{msg}\n")
        logger(f"\n--- Would send this message to {link} ---")
        logger(f"[SEND] {msg}")

        # Actually send
        try:
            sent = await client.send_message(entity, msg)
            logger(f"✓ Sent (msg id {sent.id})")
        except FloodWaitError as e:
            logger(f"Flood wait {e.seconds}s")
        except Exception as e:
            logger(f"Send error: {e}")
    else:
        logger("No message generated.")

    await client.disconnect()
    logger("\n=== Done ===")

if __name__ == "__main__":
    asyncio.run(run_one())

```

