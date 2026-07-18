import argparse
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

CLOSE_CLASS = "close_button"
START_CLASS = "start_button"
TARGET_CLASSES = {CLOSE_CLASS, START_CLASS}


class AdSkipperBot:
    def __init__(
        self,
        model_path: Path,
        adb_address: str = "127.0.0.1:5555",
        conf_threshold: float = 0.60,
        scan_interval: float = 1.5,
        click_cooldown: float = 2.0,
        anomaly_repeats: int = 5,
        anomaly_pause_s: float = 10.0,
    ) -> None:
        self.model_path = model_path
        self.model = YOLO(str(model_path))
        self.adb_address = adb_address
        self.conf_threshold = conf_threshold
        self.scan_interval = scan_interval
        self.click_cooldown = click_cooldown
        self.anomaly_repeats = anomaly_repeats
        self.anomaly_pause_s = anomaly_pause_s

        self.last_click: Optional[Tuple[int, int]] = None
        self.same_click_count = 0
        self.last_frame_hash: Optional[int] = None

        logging.info("Inicjalizacja AdSkipperBot...")
        self.connect_adb()

    def _log_model_info(self) -> None:
        """Log information about the loaded model."""
        try:
            num_classes = len(self.model.names)
            class_names = ", ".join([f"{i}={name}" for i, name in self.model.names.items()])
            logging.info("Model zaladowany - Klasy (%d): [%s]", num_classes, class_names)
            logging.info("TARGET_CLASSES szukane: %s", TARGET_CLASSES)
            
            # Log model input size
            try:
                model_input_size = self.model.model.yaml.get('imgsz', 'unknown')
                logging.info("Model expected input size: %s", model_input_size)
            except:
                pass
                
        except Exception as exc:
            logging.warning("Blad przy logowaniu informacji modelu: %s", exc)

    def _run_adb(self, args: list[str], timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        command = ["adb"] + args
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )

    def connect_adb(self) -> None:
        logging.info("Laczenie z BlueStacks przez ADB na porcie %s...", self.adb_address)
        try:
            result = self._run_adb(["connect", self.adb_address], timeout=10)
            if result.returncode == 0:
                logging.info("Polaczenie ADB powiodlo sie.")
            else:
                err_msg = result.stderr.decode(errors="ignore").strip()
                logging.warning("ADB connect zwrocil kod %s: %s", result.returncode, err_msg)
        except subprocess.TimeoutExpired:
            logging.warning("Timeout podczas laczenia ADB (10s). Kontynuujem z kolejna proba w glownej petle.")
        except Exception as exc:
            logging.warning("Blad podczas laczenia ADB: %s", exc)

    def capture_screen(self) -> Optional[np.ndarray]:
        command = ["adb", "-s", self.adb_address, "exec-out", "screencap", "-p"]
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            s_bytes, err_bytes = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            logging.warning("Timeout podczas pobierania zrzutu ekranu.")
            return None
        except FileNotFoundError:
            logging.error("Nie znaleziono komendy 'adb' w PATH.")
            return None

        if process.returncode != 0:
            err = err_bytes.decode(errors="ignore").strip()
            logging.warning("Screencap nieudany (kod %s): %s", process.returncode, err)
            return None

        nparr = np.frombuffer(s_bytes, np.uint8)
        if len(nparr) == 0:
            logging.debug("Pusty bufor - screencap nie przeslal danych.")
            return None

        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            logging.debug("cv2.imdecode zwrocil None - obrazek nie mogl byc zdekodowany.")
            return None

        logging.debug("Pomyslnie przechwycono ekran: %s", frame.shape)
        
        # Convert BGR to RGB for YOLO (OpenCV reads as BGR)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        return frame

    @staticmethod
    def frame_hash(frame: np.ndarray) -> int:
        # Szybki hash oparty na probkowaniu, wystarcza do wykrywania braku zmian.
        sampled = frame[::16, ::16]
        return hash(sampled.tobytes())

    def click(self, x: int, y: int) -> bool:
        logging.info("Akcja -> Klikniecie ADB na pozycji (%s, %s)", x, y)
        result = self._run_adb(["-s", self.adb_address, "shell", "input", "tap", str(x), str(y)], timeout=10)
        if result.returncode != 0:
            logging.warning("Nie udalo sie wykonac klikniecia: %s", result.stderr.decode(errors="ignore").strip())
            return False
        return True

    def _update_anomaly_state(self, click_point: Tuple[int, int], frame_hash_value: int) -> bool:
        if self.last_click == click_point and self.last_frame_hash == frame_hash_value:
            self.same_click_count += 1
        else:
            self.same_click_count = 1

        self.last_click = click_point
        self.last_frame_hash = frame_hash_value

        if self.same_click_count > self.anomaly_repeats:
            logging.error(
                "Wykryto potencjalna petle false-positive: punkt %s klikniety %s razy przy tym samym obrazie. Pauza %ss.",
                click_point,
                self.same_click_count,
                self.anomaly_pause_s,
            )
            time.sleep(self.anomaly_pause_s)
            self.same_click_count = 0
            return True
        
        if self.same_click_count > 1:
            logging.debug("Powtorzenie tego samego kliku: %d razy", self.same_click_count)

        return False

    def _select_click_target(self, results) -> Optional[Tuple[Tuple[int, int], str]]:
        # Priorytet: najpierw zamkniecie reklamy, potem uruchomienie kolejnej.
        best_close = None
        best_close_conf = -1.0
        best_start = None
        best_start_conf = -1.0
        total_detections = 0
        low_conf_detections = 0
        all_detections_log = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                total_detections += 1
                cls_id = int(box.cls[0])
                class_name = self.model.names[cls_id]
                confidence = float(box.conf[0])
                
                detection_info = f"{class_name}={confidence:.3f}"
                all_detections_log.append(detection_info)
                logging.info("RAW YOLO: %s", detection_info)
                
                if class_name not in TARGET_CLASSES:
                    logging.debug("  -> Ignorowane (klasa nie w TARGET_CLASSES)")
                    continue

                if confidence < self.conf_threshold:
                    low_conf_detections += 1
                    logging.debug("  -> Poniżej progu pewnosci (%.2f < %.2f)", confidence, self.conf_threshold)
                    continue

                xyxy = box.xyxy[0].cpu().numpy()
                x_click = int((xyxy[0] + xyxy[2]) / 2)
                y_click = int((xyxy[1] + xyxy[3]) / 2)

                if class_name == CLOSE_CLASS and confidence > best_close_conf:
                    best_close_conf = confidence
                    best_close = ((x_click, y_click), class_name)
                    logging.debug("  -> Nowy best close: (%.2f)", confidence)
                elif class_name == START_CLASS and confidence > best_start_conf:
                    best_start_conf = confidence
                    best_start = ((x_click, y_click), class_name)
                    logging.debug("  -> Nowy best start: (%.2f)", confidence)

        if total_detections > 0:
            logging.info("Wyniki YOLO: %d detections, %d ponizej progu | Wszystkie: [%s]", 
                        total_detections, low_conf_detections, ", ".join(all_detections_log))
        else:
            logging.info("YOLO: BRAK DETECTIONS - wszystkie klasy i progi")

        if best_close is not None:
            return best_close
        return best_start

    def run(self) -> None:
        logging.info("Bot uruchomiony. Monitorowanie reklam w tle...")
        logging.info("Model zaladowany z: %s", self.model_path)
        logging.info("Próg pewnosci: %.2f, Interwal skanowania: %.1fs", self.conf_threshold, self.scan_interval)
        self._log_model_info()

        iteration = 0
        while True:
            iteration += 1
            frame = self.capture_screen()
            if frame is None:
                logging.warning("Blad pobierania ekranu. Proba ponownego polaczenia...")
                self.connect_adb()
                time.sleep(2)
                continue

            frame_hash_value = self.frame_hash(frame)
            
            # Log frame statistics (first iteration only)
            if iteration == 1:
                logging.info("Frame stats: shape=%s, dtype=%s, min=%d, max=%d, mean=%.1f", 
                           frame.shape, frame.dtype, frame.min(), frame.max(), frame.mean())

            try:
                logging.debug("[iter %d] Uruchamianie inferencji YOLO...", iteration)
                results = self.model(frame, verbose=False, conf=self.conf_threshold)
            except Exception as exc:  # noqa: BLE001
                logging.exception("Blad podczas inferencji YOLO: %s", exc)
                time.sleep(self.scan_interval)
                continue

            target = self._select_click_target(results)

            if target is not None:
                click_point, target_class = target

                if self._update_anomaly_state(click_point, frame_hash_value):
                    continue

                logging.info("Wykryto cel klasy '%s'", target_class)
                clicked = self.click(*click_point)
                if clicked:
                    time.sleep(self.click_cooldown)
                    continue

            time.sleep(self.scan_interval)


def resolve_model_path(model_arg: str) -> Path:
    explicit_path = Path(model_arg).expanduser()
    if explicit_path.exists():
        return explicit_path.resolve()

    base_dir = Path(__file__).resolve().parent
    fallback_paths = [
        base_dir / model_arg,
        base_dir / "models" / model_arg,
        base_dir / "weights" / model_arg,
    ]

    for path in fallback_paths:
        if path.exists():
            return path.resolve()

    raise FileNotFoundError(
        f"Nie znaleziono modelu '{model_arg}'. Sprawdzone sciezki: {explicit_path}, "
        + ", ".join(str(p) for p in fallback_paths)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automatyczny skipper reklam przez ADB + YOLOv8")
    parser.add_argument("--model", default="best.pt", help="Sciezka do wag YOLOv8 (domyslnie: best.pt)")
    parser.add_argument("--adb", default="127.0.0.1:5555", help="Adres ADB emulatora")
    parser.add_argument("--conf", type=float, default=0.05, help="Prog pewnosci detekcji (domyslnie: 0.05)")
    parser.add_argument("--scan-interval", type=float, default=2.0, help="Interwal probkowania ekranu")
    parser.add_argument("--click-cooldown", type=float, default=4.0, help="Pauza po skutecznym kliknieciu")
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    configure_logging()
    args = parse_args()

    try:
        model_path = resolve_model_path(args.model)
    except FileNotFoundError as exc:
        logging.error(str(exc))
        return

    bot = AdSkipperBot(
        model_path=model_path,
        adb_address=args.adb,
        conf_threshold=args.conf,
        scan_interval=args.scan_interval,
        click_cooldown=args.click_cooldown,
    )
    bot.run()


if __name__ == "__main__":
    main()
