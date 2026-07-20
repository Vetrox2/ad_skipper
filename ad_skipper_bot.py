import argparse
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

from adb_actions import tap
from agent_config import AgentSettings
from agent_runtime import AgentRuntime
from tools.base import DetectionContext, ToolServices


class AdSkipperBot:
    def __init__(
        self,
        runtime: AgentRuntime,
        adb_address: str = "127.0.0.1:5555",
        conf_threshold: float | None = None,
        scan_interval: float | None = None,
        click_cooldown: float | None = None,
        anomaly_repeats: int | None = None,
        anomaly_pause_s: float | None = None,
    ) -> None:
        self.runtime = runtime
        self.model_path = runtime.model_path
        self.model = YOLO(str(runtime.model_path))
        self.adb_address = adb_address
        self.conf_threshold = conf_threshold if conf_threshold is not None else runtime.settings.conf_threshold
        self.scan_interval = scan_interval if scan_interval is not None else runtime.settings.scan_interval
        self.click_cooldown = click_cooldown if click_cooldown is not None else runtime.settings.click_cooldown
        self.anomaly_repeats = anomaly_repeats if anomaly_repeats is not None else runtime.settings.anomaly_repeats
        self.anomaly_pause_s = anomaly_pause_s if anomaly_pause_s is not None else runtime.settings.anomaly_pause_s

        self.last_click: Optional[Tuple[int, int]] = None
        self.same_click_count = 0
        self.last_frame_hash: Optional[int] = None
        self.logger = logging.getLogger(__name__)
        self.services = ToolServices(click=lambda x, y: tap(self.adb_address, x, y), sleep=time.sleep, logger=self.logger)

        logging.info("Inicjalizacja AdSkipperBot...")
        self.connect_adb()

    def _log_model_info(self) -> None:
        """Log information about the loaded model."""
        try:
            num_classes = len(self.model.names)
            class_names = ", ".join([f"{i}={name}" for i, name in self.model.names.items()])
            logging.info("Model zaladowany - Klasy (%d): [%s]", num_classes, class_names)
            logging.info("Tooly dla klas: %s", ", ".join(sorted(self.runtime.tools_by_class)))
            
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

    def _select_click_target(self, results) -> Optional[DetectionContext]:
        best_target: Optional[DetectionContext] = None
        best_rank: tuple[int, float] = (-10**9, -1.0)
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
                
                if class_name not in self.runtime.tools_by_class:
                    logging.debug("  -> Ignorowane (brak toola dla klasy)")
                    continue

                if confidence < self.conf_threshold:
                    low_conf_detections += 1
                    logging.debug("  -> Poniżej progu pewnosci (%.2f < %.2f)", confidence, self.conf_threshold)
                    continue

                xyxy = box.xyxy[0].cpu().numpy()
                x_click = int((xyxy[0] + xyxy[2]) / 2)
                y_click = int((xyxy[1] + xyxy[3]) / 2)

                tool_definition = self.runtime.tool_definitions[class_name]
                candidate = DetectionContext(
                    class_name=class_name,
                    confidence=confidence,
                    bounding_box=(int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])),
                    center=(x_click, y_click),
                    frame_hash=0,
                    iteration=0,
                    agent_root=self.runtime.agent_dir,
                    frame=None,
                    extras={
                        "tool_path": str(tool_definition.tool_path),
                        "tool_class": tool_definition.tool_class,
                        "priority": tool_definition.priority,
                        **tool_definition.params,
                    },
                )

                candidate_rank = (tool_definition.priority, confidence)
                if candidate_rank > best_rank:
                    best_rank = candidate_rank
                    best_target = candidate
                    logging.debug(
                        "  -> Nowy best target: %s (priority=%s, confidence=%.2f)",
                        class_name,
                        tool_definition.priority,
                        confidence,
                    )

        if total_detections > 0:
            logging.info("Wyniki YOLO: %d detections, %d ponizej progu | Wszystkie: [%s]", 
                        total_detections, low_conf_detections, ", ".join(all_detections_log))
        else:
            logging.info("YOLO: BRAK DETECTIONS - wszystkie klasy i progi")

        return best_target

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
                target.frame = frame
                target.frame_hash = frame_hash_value
                target.iteration = iteration

                if self._update_anomaly_state(target.center, frame_hash_value):
                    continue

                tool = self.runtime.tools_by_class.get(target.class_name)
                if tool is None:
                    logging.warning("Brak toola dla wykrytej klasy '%s'", target.class_name)
                    time.sleep(self.scan_interval)
                    continue

                logging.info("Wykryto cel klasy '%s'", target.class_name)
                result = tool.handle(target, self.services)
                if result.handled:
                    sleep_s = result.sleep_s if result.sleep_s is not None else self.click_cooldown
                    time.sleep(sleep_s)
                    continue

            time.sleep(self.scan_interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automatyczny skipper reklam przez ADB + YOLOv8")
    parser.add_argument("--agent-dir", default="models", help="Katalog agenta z config.json i best.pt")
    parser.add_argument("--model", default=None, help="Opcjonalna bezposrednia sciezka do wag YOLOv8")
    parser.add_argument("--adb", default="127.0.0.1:5555", help="Adres ADB emulatora")
    parser.add_argument("--conf", type=float, default=None, help="Prog pewnosci detekcji (domyslnie: wartosc z AgentSettings, 0.90)")
    parser.add_argument("--scan-interval", type=float, default=2.0, help="Interwal probkowania ekranu")
    parser.add_argument("--click-cooldown", type=float, default=4.0, help="Pauza po skutecznym kliknieciu")
    parser.add_argument("--anomaly-repeats", type=int, default=5, help="Liczba powtorzen klikniecia przed pauza")
    parser.add_argument("--anomaly-pause", type=float, default=10.0, help="Pauza po wykryciu petli false-positive")
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
        settings_kwargs = {
            "scan_interval": args.scan_interval,
            "click_cooldown": args.click_cooldown,
            "anomaly_repeats": args.anomaly_repeats,
            "anomaly_pause_s": args.anomaly_pause,
        }
        if args.conf is not None:
            settings_kwargs["conf_threshold"] = args.conf
        agent_settings = AgentSettings(**settings_kwargs)
        agent_runtime = AgentRuntime.from_agent_dir(
            Path(args.agent_dir),
            settings=agent_settings,
            model_override=args.model,
        )
    except FileNotFoundError as exc:
        logging.error(str(exc))
        return
    except Exception as exc:
        logging.error("Nie udalo sie wczytac agenta: %s", exc)
        return

    bot = AdSkipperBot(
        runtime=agent_runtime,
        adb_address=args.adb,
    )
    bot.run()


if __name__ == "__main__":
    main()