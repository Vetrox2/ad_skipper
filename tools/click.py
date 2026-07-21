from __future__ import annotations

from tools.base import BaseTool, DetectionContext, ToolResult, ToolServices


class ClickTool(BaseTool):
    def handle(self, context: DetectionContext, services: ToolServices) -> ToolResult:
        tap_point = self.config.get("tap_point")
        x, y = context.center

        if isinstance(tap_point, (list, tuple)) and len(tap_point) == 2:
            x = int(tap_point[0])
            y = int(tap_point[1])

        services.logger.info("Tool click -> %s at (%s, %s)", context.class_name, x, y)
        if services.click(x, y):
            sleep_s = self.config.get("sleep_s", self.config.get("cooldown_s"))
            return ToolResult(handled=True, sleep_s=sleep_s, message=f"clicked {context.class_name}, waiting {sleep_s}s")
        return ToolResult(handled=False, message=f"click failed for {context.class_name}")