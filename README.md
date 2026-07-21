# ad_skipper

Automatyczny skipper reklam dla BlueStacks oparty o ADB i YOLOv8.

## Wymagania

- Python 3.10+
- `adb` dostepne w `PATH`
- Dzialajacy emulator BlueStacks z wlaczonym debugowaniem ADB
- Wytrenowany model YOLOv8 i `config.json` w katalogu agenta

## Instalacja

1. Zainstaluj zaleznosci:

	```bash
	pipenv install
	```

2. Umiesc katalog agenta, np. `models/badoo/`, z plikami `best.pt` i `config.json`.

## Przygotowanie danych

Wrzuciłeś surowy eksport z Roboflow do `dataset/`:
```
├── dataset/           ← TU rozpakuj zip
│   ├── data.yaml
│   ├── train/
│   │   ├── images/
│   │   └── labels/
│   ├── valid/
│   │   ├── images/
│   │   └── labels/
│   └── test/
│       ├── images/
│       └── labels/
└── runs/detect/train-{x}/weights    ← tu wyląduje wytrenowany best.pt
```

## Trenowanie

```bash
pipenv run yolo detect train data=dataset/data.yaml model=yolov8n.pt epochs=100 imgsz=640
```

Po treningu skopiuj `best.pt` do katalogu agenta i dodaj `config.json` z mapowaniem klas na toole.

## Uruchomienie

```bash
pipenv run python ad_skipper_bot.py --agent-dir models/badoo --adb 127.0.0.1:5555
```

Przydatne parametry:

- `--conf 0.05` - prog pewnosci detekcji (domyslnie: 0.05, dla nowego modelu mozna zwiększyć)
- `--scan-interval 2.0` - interwal probkowania ekranu (domyslnie: 2s)
- `--click-cooldown 4.0` - pauza po kliknieciu (domyslnie: 4.0s, zwiększ aby nie klika zbyt szybko)
- `--agent-dir models/badoo` - uruchomienie konkretnego agenta z wlasnym `best.pt` i `config.json`

## Toole

Toole (np. `tools/click.py`) sa wspoldzielone przez wszystkich agentow i leza w
katalogu `tools/` w korzeniu projektu — nie kopiuje sie ich do kazdego
`models/<agent>/`. Sciezka `tool_path` w `config.json` jest wiec rozwiazywana
w tej kolejnosci:

1. wzgledem `tools/` w korzeniu projektu (typowy przypadek, np. `tools/click.py`),
2. jesli tam nie istnieje — wzgledem katalogu agenta (np. `models/badoo/tools/`),
   co pozwala danemu agentowi miec wlasny, niestandardowy tool.

## Struktura agenta

Przyklad katalogu agenta:

```text
models/badoo/
├── best.pt
└── config.json
```

Przyklad `config.json`:

```json
[
	{
		"class": "close_button",
		"tool_path": "tools/click.py",
		"tool_class": "ClickTool",
		"priority": 100
	},
	{
		"class": "start_button",
		"tool_path": "tools/click.py",
		"tool_class": "ClickTool",
		"priority": 50
	}
]
```

Tool dostaje standardowy kontekst detekcji: nazwe klasy, confidence, bounding box, srodek, numer iteracji, hash ramki i `extras` na dane specyficzne dla toola. Kazdy tool dziedziczy po bazowej klasie `BaseTool` i implementuje `handle(context, services)`.

### SwitchAppTool (`tools/switch_app.py`)

Sluzy do wracania do aplikacji docelowej, gdy reklama mimo klikniecia w
`close_button` i tak przekierowala do innej aplikacji (typowo Google Play).
Po wykryciu skonfigurowanej klasy (np. `google_play_store`) przelacza z
powrotem na aplikacje podana w `params.package` - karty nowej aplikacji nie
trzeba zamykac, ale mozna to opcjonalnie wlaczyc przez `close_source_package`.

Przyklad wpisu w `config.json`:

```json
{
	"class": "google_play_store",
	"tool_path": "tools/switch_app.py",
	"tool_class": "SwitchAppTool",
	"priority": 200,
	"params": {
		"package": "com.badoo.mobile",
		"sleep_s": 2.0,
		"close_source_package": "com.android.vending"
	}
}
```

Uwagi:

- `package` to package_name aplikacji docelowej (sprawdz dokladna wartosc np. przez `adb shell pm list packages | grep badoo`).
- `priority` warto ustawic wysoko, zeby ta klasa wygrywala, jesli akurat nakladalaby sie z innymi wykryciami na tej samej klatce.
- `close_source_package` jest opcjonalne (np. `com.android.vending` dla Google Play) i domyslnie nieaktywne - gdy podane, po przelaczeniu bot dodatkowo force-stopuje te aplikacje.

## Zabezpieczenia

- Auto-reconnect ADB po bledzie pobrania ramki.
- Wykrywanie zapetlenia false-positive: gdy ten sam punkt jest klikany wielokrotnie przy niezmienionym obrazie, bot robi 10 sekund przerwy.