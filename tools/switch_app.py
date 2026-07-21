from __future__ import annotations

from tools.base import BaseTool, DetectionContext, ToolResult, ToolServices


class SwitchAppTool(BaseTool):
    """Tool wykrywajacy 'wypadniecie' do obcej aplikacji (np. strony Google
    Play, na ktora reklama przekierowala mimo klikniecia w 'close_button') i
    przelaczajacy z powrotem na aplikacje docelowa.

    Oczekiwane pola w `params` (config.json):
      - package (wymagane): package_name aplikacji docelowej, np. "com.badoo.mobile".
        (mozna tez uzyc aliasu "target_package")
      - sleep_s / cooldown_s (opcjonalne): pauza po udanym przelaczeniu.
      - close_source_package (opcjonalne): package_name aplikacji, z ktorej
        bot sie przelacza (np. "com.android.vending" dla Google Play) - jesli
        podany, zostanie ona dodatkowo force-stopowana po przelaczeniu
        (opcjonalny "premium bonus" - domyslnie wylaczone, karty nie trzeba
        zamykac).
    """

    def handle(self, context: DetectionContext, services: ToolServices) -> ToolResult:
        package_name = self.config.get("package") or self.config.get("target_package")
        if not package_name:
            services.logger.warning(
                "SwitchAppTool: brak pola 'package' w params dla klasy '%s' - pomijam.",
                context.class_name,
            )
            return ToolResult(handled=False, message=f"missing target package for {context.class_name}")

        if services.switch_app is None:
            services.logger.warning("SwitchAppTool: brak skonfigurowanego services.switch_app.")
            return ToolResult(handled=False, message="switch_app service not configured")

        services.logger.info(
            "Tool switch_app -> wykryto '%s', przelaczam z powrotem na: %s",
            context.class_name,
            package_name,
        )

        if not services.switch_app(package_name):
            return ToolResult(handled=False, message=f"switch to {package_name} failed")

        close_source_package = self.config.get("close_source_package")
        if close_source_package and services.close_app is not None:
            services.close_app(close_source_package)

        sleep_s = self.config.get("sleep_s", self.config.get("cooldown_s"))
        return ToolResult(handled=True, sleep_s=sleep_s, message=f"switched to {package_name}")
