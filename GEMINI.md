# Projekt: Ad Skipper

Automatyczny skipper reklam dla BlueStacks wykorzystujący ADB oraz model detekcji obrazu YOLOv8.

## Struktura projektu
- `src/ad_skipper/bot.py` - Główna pętla programu pobierająca obrazki z ADB i odpytująca YOLO.
- `src/ad_skipper/adb.py` - Klasy obsługujące połączenie z emulatorem przez ADB (`pure-python-adb`).
- `src/ad_skipper/tools/` - Wbudowane "narzędzia" wykonujące akcje po wykryciu obiektu:
  - `base.py` - Klasa bazowa `BaseTool`.
  - `click.py` - Narzędzie do klikania w wyznaczony punkt.
  - `switch_app.py` - Narzędzie powracające do docelowej aplikacji, gdy reklama wymusi wyjście.
- `src/ad_skipper/gui/` - Moduł GUI (PySide6):
  - `__main_gui__.py` - Entry point GUI (uruchamia `MainWindow`).
  - `main_window.py` - Główne okno aplikacji (QMainWindow): combobox modelu, logi, Start/Stop/Pauza.
  - `bot_worker.py` - `BotWorker(QThread)` opakowujący `AdSkipperBot` z obsługą `stop_event`/`pause_event`.
  - `log_handler.py` - `QtLogHandler` – bridge między `logging` a sygnałem Qt (`log_line`).
  - `model_scanner.py` - `list_agents()` skanuje `models/` i zwraca listę `AgentEntry`.
- `models/<agent_name>/` - Katalogi zawierające plik wag modelu `best.pt` oraz definicję akcji `config.json` przypisanych do detekcji.
- `dataset/` - Katalog na surowe zbiory danych YOLO (np. z Roboflow).
- `runs/` - Katalog wynikowy z procesu trenowania YOLO.
- `dist/` - Katalog zawierający zbudowane paczki dystrybucyjne (`dist/ad_skipper_v<wersja>/`).
- `build.py` - Skrypt budujący dystrybucję .exe przez PyInstallera z wersjonowaniem.
- `ad_skipper.spec` - Specyfikacja PyInstallera (entry point: GUI; zbiera ultralytics, torch, cv2, PySide6).
- `VERSION` - Plik przechowujący bieżącą wersję projektu.
- `01_plan_build_exe.md`, `02_plan_gui.md` - Notatki/plany rozwoju projektu.

## Uruchamianie i Budowanie
Projekt używa `pipenv` do zarządzania środowiskiem (Python 3.12.2).
- Instalacja: `pipenv install`
- Uruchomienie GUI: `pipenv run gui`
- Uruchomienie skippera (CLI): `pipenv run start --agent-dir models/badoo --adb 127.0.0.1:5555`
  (lub bezpośrednio: `python -m src.ad_skipper ...`)
- Trenowanie YOLO: `pipenv run yolo detect train data=dataset/data.yaml model=yolov8n.pt epochs=100 imgsz=640`
- Budowanie wersji produkcyjnej (.exe):
  - `pipenv run build` (lub `python build.py`) – automatycznie podbija wersję minor (+1)
  - `python build.py 1.0.0` (lub `-v 1.0.0` / `--version 1.0.0`) – buduje ze wskazaną wersją
  - Paczka wynikowa trafia do `dist/ad_skipper_v<wersja>/` (zawiera `.exe`, `_internal/`, `tools/`, `models/`, `.env`, `README.txt`).
  - Build produkuje exe GUI (bez konsoli); tryb CLI nadal dostępny lokalnie przez `pipenv run start`.


## Architektura Toole & Konfiguracja
Każdy model definiuje logikę w `config.json`:
```json
[
  {
    "class": "close_button",
    "tool_path": "src.ad_skipper.tools.click",
    "tool_class": "ClickTool",
    "priority": 100
  }
]
```
Narzędzia otrzymują `context` (klasę, confidence, pozycję bounding box, środek ekranu itp.) i wykonują akcje. Katalog bazowy z narzędziami to `src/ad_skipper/tools/` (uwaga: starsza dokumentacja może wskazywać na `tools/`).

## AI Guidelines (Wytyczne optymalizacji kodu / oszczędzania tokenów)
- Odpowiadaj zwięźle, dostarczaj tylko żądany kod lub modyfikacje, pomijaj niepotrzebne wyjaśnienia.
- Nie tłumacz oczywistych koncepcji z Pythona, YOLO czy ADB, chyba że o to poproszono.
- Modyfikując klasę lub funkcję pokazuj głównie to, co ulega zmianie, pomijaj resztę ciała pliku jeśli nie jest to konieczne do zrozumienia szerszego kontekstu.
- Skupiaj się na modułowości – zachowaj podział na klasę `BaseTool` i zunifikowany interfejs.
- Pisz kod zgodny z typowaniem statycznym w Pythonie.
