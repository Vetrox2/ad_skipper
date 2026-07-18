# ad_skipper

Automatyczny skipper reklam dla BlueStacks oparty o ADB i YOLOv8.

## Wymagania

- Python 3.10+
- `adb` dostepne w `PATH`
- Dzialajacy emulator BlueStacks z wlaczonym debugowaniem ADB
- Wytrenowany model YOLOv8 z klasami: `close_button`, `start_button`

## Instalacja

1. Zainstaluj zaleznosci:

	```bash
	pipenv install
	```

2. Umiesc plik modelu (np. `best.pt`) w katalogu projektu, `models/` albo `weights/`.

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

Po treningu skopiuj best.pt do folderu models/

## Uruchomienie

```bash
pipenv run python ad_skipper_bot.py --model best.pt --adb 127.0.0.1:5555
```

Przydatne parametry:

- `--conf 0.05` - prog pewnosci detekcji (domyslnie: 0.05, dla nowego modelu mozna zwiększyć)
- `--scan-interval 2.0` - interwal probkowania ekranu (domyslnie: 2s)
- `--click-cooldown 4.0` - pauza po kliknieciu (domyslnie: 4.0s, zwiększ aby nie klika zbyt szybko)

## Zabezpieczenia

- Auto-reconnect ADB po bledzie pobrania ramki.
- Wykrywanie zapetlenia false-positive: gdy ten sam punkt jest klikany wielokrotnie przy niezmienionym obrazie, bot robi 10 sekund przerwy.