# SPECYFIKACJA PROJEKTU: Automatyczny Skipper Reklam w BlueStacks (ADB + YOLOv8)

## 1. Cel i Opis Projektu

Celem projektu jest stworzenie lekkiego i stabilnego skryptu automatyzacji w języku Python, który działa całkowicie w tle. Skrypt łączy się z instancją emulatora BlueStacks za pomocą Android Debug Bridge (ADB), pobiera zrzuty ekranu bezpośrednio z pamięci wirtualnej systemu Android, a następnie wykorzystuje dedykowany model detekcji obiektów **YOLOv8** do identyfikacji elementów interfejsu reklamowego (takich jak przyciski zamknij "X", napisy "Pomiń" oraz liczniki czasu). Po wykryciu celu, aplikacja wysyła precyzyjne komendy kliknięcia przez ADB. Dzięki temu program nie potrzebuje aktywnego okna i nie przeszkadza użytkownikowi w normalnym korzystaniu z myszy i klawiatury na komputerze.

---

## 2. Architektura Środowiska i Tech-Stack

Projekt musi zostać uruchomiony w izolowanym środowisku wirtualnym z wykorzystaniem menedżera pakietów, który jest już dostępny na maszynie docelowej.

### Konfiguracja Środowiska (Wymagania dla Agenta AI)

* **Wirtualne Środowisko:** Standardowe `.venv` zintegrowane i zarządzane przez `pipenv`.
* **Zarządzanie Zależnościami:** Plik `Pipfile` definiujący pakiety i sekcje `packages`.

### Wymagane Biblioteki (Pipfile)

* `python_version` = "3.10" (lub nowszy)
* `ultralytics` (Inferencja modelu YOLOv8)
* `pure-python-adb` (Komunikacja z emulatorem w Pythonie)
* `opencv-python` (Przetwarzanie obrazu i operacje na matrycach)
* `pillow` (Konwersje formatów obrazów)

---

## 3. Plik Konfiguracyjny Zależności: `Pipfile`

Agent AI powinien wygenerować w katalogu głównym projektu poniższy plik `Pipfile`, a następnie zainstalować środowisko komendą `pipenv install`:

```toml
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]
ultralytics = "*"
pure-python-adb = "*"
opencv-python = "*"
pillow = "*"

[dev-packages]

[requires]
python_version = "3.10"

```

---

## 4. Architektura Systemu i Workflow

Algorytm działa w nieskończonej pętli opartej na Maszynie Stanów (FSM):

1. **Pobranie ekranu przez ADB:** Pobranie surowego bufora ramki z Androida bezpośrednio do pamięci RAM skryptu (pominięcie powolnego zapisu na dysku twardym).
2. **Preprocesing obrazu:** Opcjonalne pocięcie obrazu na kluczowe obszary zainteresowania (np. rogi ekranu, gdzie najczęściej pojawiają się przyciski zamknięcia).
3. **Inferencja YOLOv8:** Przekazanie obrazu do modelu w celu detekcji klas: `close_x`, `skip_btn`, `timer`.
4. **Moduł Egzekucji:** Wyliczenie środka geometrycznego znalezionego obiektu i wysłanie komendy kliknięcia `input tap` przez protokół ADB.
5. **Mechanizm Cooldown / Backoff:** Jeśli obiekt zostanie kliknięty – następuje pauza w celu odświeżenia stanu aplikacji. Jeśli nic nie zostanie znalezione – skrypt usypia się na krótki interwał przed kolejną próbą.

---

## 5. Gotowy Kod Implementacyjny (Szkielet Bot-a)

Poniższy skrypt stanowi bazę produkcyjną dla bota. Agent AI musi go rozbudować o obsługę błędów i dynamiczne ścieżki do modelu.

```python
import cv2
import numpy as np
import subprocess
import time
from ultralytics import YOLO

class AdSkipperBot:
    def __init__(self, model_path="best.pt", adb_address="127.0.0.1:5555"):
        self.model = YOLO(model_path)
        self.adb_address = adb_address
        self.connect_adb()

    def connect_adb(self):
        print(f"Łączenie z BlueStacks przez ADB na porcie {self.adb_address}...")
        subprocess.run(["adb", "connect", self.adb_address], stdout=subprocess.DEVNULL)
        
    def capture_screen(self):
        # Optymalizacja strumienia: Zrzut ekranu bezpośrednio do pamięci RAM
        command = ["adb", "-s", self.adb_address, "exec-out", "screencap", "-p"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        s_bytes, _ = process.communicate()
        
        nparr = np.frombuffer(s_bytes, np.uint8)
        if len(nparr) == 0:
            return None
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return frame

    def click(self, x, y):
        print(f"Akcja -> Wysyłanie kliknięcia ADB na pozycję ({x}, {y})")
        subprocess.run(["adb", "-s", self.adb_address, "shell", "input", "tap", str(x), str(y)], stdout=subprocess.DEVNULL)

    def run(self):
        print("Bot uruchomiony pomyślnie. Monitorowanie reklam w tle...")
        while True:
            frame = self.capture_screen()
            if frame is None:
                print("Błąd pobierania ekranu. Próba ponownego połączenia...")
                self.connect_adb()
                time.sleep(2)
                continue

            # Inferencja YOLO (stream=True optymalizuje zarządzanie pamięcią VRAM/RAM)
            results = self.model(frame, verbose=False, conf=0.60)
            
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    cls_id = int(box.cls[0])
                    class_name = self.model.names[cls_id]
                    xyxy = box.xyxy[0].cpu().numpy()
                    
                    if class_name in ["close_x", "skip_btn"]:
                        # Obliczanie środka geometrycznego ramki otaczającej (Bounding Box)
                        x_click = int((xyxy[0] + xyxy[2]) / 2)
                        y_click = int((xyxy[1] + xyxy[3]) / 2)
                        
                        self.click(x_click, y_click)
                        time.sleep(2.0)  # Cooldown po kliknięciu na przeładowanie widoku
                        break
            
            time.sleep(1.5)  # Częstotliwość próbkowania ekranu

if __name__ == "__main__":
    # Uruchomienie bota po dostarczeniu wytrenowanego pliku 'best.pt'
    bot = AdSkipperBot(model_path="best.pt", adb_address="127.0.0.1:5555")
    # bot.run()

```

---

## 6. Sytuacje Krytyczne i Zabezpieczenia dla Agenta

* **Zerwanie połączenia ADB:** Podczas długiej pracy emulator potrafi zresetować mostek ADB. Skrypt musi przechwytywać puste ramki (`None`) i automatycznie wywoływać procedurę `connect_adb()`.
* **Pętla fałszywych kliknięć (False Positives):** Jeśli element gry graficznie przypomina krzyżyk "X", YOLO może klikać go w nieskończoność. Agent musi zaimplementować licznik: jeśli skrypt kliknie dokładnie te same współrzędne więcej niż 5 razy z rzędu, a obraz nie ulegnie zmianie, aplikacja musi zgłosić anomalie i wstrzymać działanie na 10 sekund.
* **Skalowanie rozdzielczości:** Baza danych do uczenia modelu YOLO musi być zbierana w tej samej proporcji ekranu (Aspect Ratio), w jakiej uruchomiony jest BlueStacks, aby uniknąć przesunięć punktu kliknięcia względem wykrytego obiektu.