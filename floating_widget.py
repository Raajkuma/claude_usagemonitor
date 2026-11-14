import sys
import math
from datetime import datetime
from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPointF, QPropertyAnimation, QEasingCurve, pyqtProperty
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QAction, QLinearGradient,
    QRadialGradient, QPainterPath, QPolygonF
)
from PyQt6.QtWidgets import QApplication, QWidget, QMenu
from usage_service import get_claude_usage
from settings_dialog import SettingsDialog
from config import load_config, save_config


class JarvisHUDWidget(QWidget):
    # Compact & Expanded geometry matching your reference layouts
    COMPACT_W, COMPACT_H = 380, 148
    EXPANDED_W, EXPANDED_H = 420, 500

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.is_expanded = False
        self.usage_data = get_claude_usage()

        # Animation state
        self.anim_mode = "ORBIT"  # ORBIT | SCAN | PULSE
        self.anim_paused = False
        self.angle_outer = 0.0
        self.angle_inner = 0.0
        self.pulse_phase = 0.0

        # Smooth geometry properties
        self._anim_w = float(self.COMPACT_W)
        self._anim_h = float(self.COMPACT_H)

        # Interactive hitboxes for expanded footer controls
        self.mode_rects = {}
        self.pause_rect = QRectF()
        self.collapse_rect = QRectF()

        self.init_ui()

        # Poll local Claude session files every 5 seconds for real-time updates
        self.usage_timer = QTimer(self)
        self.usage_timer.timeout.connect(self.update_usage)
        self.usage_timer.start(5000)

        # 40 FPS render loop
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self.tick_animation)
        self.render_timer.start(25)

        # Smooth spring-curve resize animations
        self.anim_width = QPropertyAnimation(self, b"anim_w")
        self.anim_width.setDuration(320)
        self.anim_width.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.anim_height = QPropertyAnimation(self, b"anim_h")
        self.anim_height.setDuration(320)
        self.anim_height.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.update_click_through()
        self.setGeometry(
            self.config.get("x", 100),
            self.config.get("y", 100),
            self.COMPACT_W,
            self.COMPACT_H,
        )

    def update_click_through(self):
        if self.config.get("click_through", False):
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowTransparentForInput)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowTransparentForInput)
        self.show()

    def update_usage(self):
        self.usage_data = get_claude_usage()
        self.update()

    def tick_animation(self):
        if not self.anim_paused:
            if self.anim_mode == "ORBIT":
                self.angle_outer = (self.angle_outer + 1.1) % 360
                self.angle_inner = (self.angle_inner - 1.6) % 360
            elif self.anim_mode == "SCAN":
                self.angle_outer = (self.angle_outer + 2.8) % 360
                self.angle_inner = (self.angle_inner + 2.8) % 360
            elif self.anim_mode == "PULSE":
                self.angle_outer = (self.angle_outer + 0.4) % 360
            self.pulse_phase = (self.pulse_phase + 0.08) % (2 * math.pi)
        self.update()

    # Animated dimension properties
    def get_anim_w(self):
        return self._anim_w

    def set_anim_w(self, val):
        self._anim_w = val
        self.resize(int(val), int(self._anim_h))

    anim_w = pyqtProperty(float, get_anim_w, set_anim_w)

    def get_anim_h(self):
        return self._anim_h

    def set_anim_h(self, val):
        self._anim_h = val
        self.resize(int(self._anim_w), int(val))

    anim_h = pyqtProperty(float, get_anim_h, set_anim_h)

    def toggle_expand(self):
        self.is_expanded = not self.is_expanded
        self.anim_width.stop()
        self.anim_height.stop()

        self.anim_width.setStartValue(float(self.width()))
        self.anim_width.setEndValue(float(self.EXPANDED_W if self.is_expanded else self.COMPACT_W))

        self.anim_height.setStartValue(float(self.height()))
        self.anim_height.setEndValue(float(self.EXPANDED_H if self.is_expanded else self.COMPACT_H))

        self.anim_width.start()
        self.anim_height.start()

    # Mouse interactions
    def mousePressEvent(self, event):
        pos = event.position()
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_expanded:
                if self.collapse_rect.contains(pos):
                    self.toggle_expand()
                    return
                if self.pause_rect.contains(pos):
                    self.anim_paused = not self.anim_paused
                    self.update()
                    return
                for mode, rect in self.mode_rects.items():
                    if rect.contains(pos):
                        self.anim_mode = mode
                        self.update()
                        return

            self.old_pos = event.globalPosition().toPoint()
            self._drag_moved = False

        elif event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if hasattr(self, "old_pos") and self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            if delta.manhattanLength() > 3:
                self._drag_moved = True
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()
            self.config["x"] = self.x()
            self.config["y"] = self.y()
            save_config(self.config)

    def mouseReleaseEvent(self, event):
        # Single click (without dragging) toggles expand/collapse
        if event.button() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_moved"):
            if not self._drag_moved and not self.is_expanded:
                self.toggle_expand()
        self.old_pos = None

    def show_context_menu(self, pos):
        menu = QMenu(self)
        toggle_act = QAction("Collapse HUD" if self.is_expanded else "Expand HUD", self)
        toggle_act.triggered.connect(self.toggle_expand)
        settings_act = QAction("HUD Settings", self)
        settings_act.triggered.connect(self.open_settings)
        exit_act = QAction("Close HUD", self)
        exit_act.triggered.connect(QApplication.quit)

        menu.addAction(toggle_act)
        menu.addAction(settings_act)
        menu.addSeparator()
        menu.addAction(exit_act)
        menu.exec(pos)

    def open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self.config = load_config()
            self.update_click_through()
            self.update()

    # --- RENDERING HELPERS ---

    def _draw_glossy_chassis(self, painter: QPainter, rect: QRectF):
        """Draws the translucent dark-slate glass frame with top sheen & amber corner brackets."""
        amber = QColor(245, 166, 35)
        amber_dim = QColor(245, 166, 35, 70)

        # 1. Translucent dark glass base (lets desktop/editor subtly show through)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        bg_grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg_grad.setColorAt(0.0, QColor(28, 30, 34, 185))   # Translucent charcoal top
        bg_grad.setColorAt(0.45, QColor(18, 20, 23, 175))  # Translucent mid glass
        bg_grad.setColorAt(1.0, QColor(12, 13, 15, 190))   # Deep translucent base
        painter.fillPath(path, QBrush(bg_grad))

        # 2. Glossy glass specular reflection on upper 38%
        gloss_rect = QRectF(rect.left() + 1, rect.top() + 1, rect.width() - 2, rect.height() * 0.38)
        gloss_path = QPainterPath()
        gloss_path.addRoundedRect(gloss_rect, 9, 9)
        gloss_grad = QLinearGradient(gloss_rect.topLeft(), gloss_rect.bottomLeft())
        gloss_grad.setColorAt(0.0, QColor(255, 255, 255, 26))
        gloss_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(gloss_path, QBrush(gloss_grad))

        # 3. Outer subtle rim + inner hairline border
        painter.setPen(QPen(QColor(245, 166, 35, 130), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 10, 10)

        inner_rect = rect.adjusted(4, 4, -4, -4)
        painter.setPen(QPen(amber_dim, 0.8))
        painter.drawRoundedRect(inner_rect, 7, 7)

        # 4. Chamfered Amber Corner Brackets (Top-Left, Top-Right, Bottom-Left)
        painter.setBrush(QBrush(amber))
        painter.setPen(Qt.PenStyle.NoPen)
        L = 18.0
        T = 3.0

        # Top-Left bracket
        tl = QPolygonF([
            QPointF(rect.left(), rect.top()),
            QPointF(rect.left() + L, rect.top()),
            QPointF(rect.left() + L - 3, rect.top() + T),
            QPointF(rect.left() + T, rect.top() + T),
            QPointF(rect.left() + T, rect.top() + L - 3),
            QPointF(rect.left(), rect.top() + L),
        ])
        painter.drawPolygon(tl)

        # Top-Right bracket
        tr = QPolygonF([
            QPointF(rect.right(), rect.top()),
            QPointF(rect.right() - L, rect.top()),
            QPointF(rect.right() - L + 3, rect.top() + T),
            QPointF(rect.right() - T, rect.top() + T),
            QPointF(rect.right() - T, rect.top() + L - 3),
            QPointF(rect.right(), rect.top() + L),
        ])
        painter.drawPolygon(tr)

        # Bottom-Left bracket
        bl = QPolygonF([
            QPointF(rect.left(), rect.bottom()),
            QPointF(rect.left() + L, rect.bottom()),
            QPointF(rect.left() + L - 3, rect.bottom() - T),
            QPointF(rect.left() + T, rect.bottom() - T),
            QPointF(rect.left() + T, rect.bottom() - L + 3),
            QPointF(rect.left(), rect.bottom() - L),
        ])
        painter.drawPolygon(bl)

    def _draw_reactor_core(self, painter: QPainter, cx: float, cy: float, radius: float):
        """Renders the glowing amber concentric radar core with radial spokes & outer ticks."""
        amber = QColor(245, 166, 35)
        pulse_scale = 1.0 + (0.08 * math.sin(self.pulse_phase) if self.anim_mode == "PULSE" else 0.0)
        r = radius * pulse_scale

        # Soft radial ambient glow
        glow = QRadialGradient(QPointF(cx, cy), r * 1.15)
        glow.setColorAt(0.0, QColor(245, 166, 35, 75))
        glow.setColorAt(0.55, QColor(245, 166, 35, 22))
        glow.setColorAt(1.0, QColor(245, 166, 35, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), r * 1.15, r * 1.15)

        # Outer dashed orbit ring + 3 chunky orbital markers (120 deg apart)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.angle_outer)

        dash_pen = QPen(QColor(245, 166, 35, 110), 1.0, Qt.PenStyle.DashLine)
        painter.setPen(dash_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0, 0), r, r)

        painter.setBrush(QBrush(amber))
        painter.setPen(Qt.PenStyle.NoPen)
        for deg in (-90, 30, 150):
            painter.save()
            painter.rotate(deg)
            painter.drawRoundedRect(QRectF(r - 4, -2.5, 7, 5), 1.5, 1.5)
            painter.restore()
        painter.restore()

        # Mid segmented arc ring + 3 radial turbine spokes
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.angle_inner)

        mid_r = r * 0.72
        arc_pen = QPen(amber, 2.2)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        arc_box = QRectF(-mid_r, -mid_r, mid_r * 2, mid_r * 2)
        for start_deg in (15, 135, 255):
            painter.drawArc(arc_box, start_deg * 16, 85 * 16)

        # 3 glowing radial spokes connecting inner ring to mid ring
        inner_r = r * 0.34
        spoke_pen = QPen(QColor(245, 166, 35, 180), 1.8)
        painter.setPen(spoke_pen)
        for deg in (0, 120, 240):
            rad = math.radians(deg)
            painter.drawLine(
                QPointF(math.cos(rad) * inner_r, math.sin(rad) * inner_r),
                QPointF(math.cos(rad) * mid_r, math.sin(rad) * mid_r),
            )
        painter.restore()

        # Inner static ring & hot glowing core orb
        inner_r = r * 0.34
        painter.setPen(QPen(QColor(255, 210, 110, 200), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), inner_r, inner_r)

        core_glow = QRadialGradient(QPointF(cx, cy), inner_r * 0.65)
        core_glow.setColorAt(0.0, QColor(255, 245, 200, 255))
        core_glow.setColorAt(0.6, QColor(245, 166, 35, 230))
        core_glow.setColorAt(1.0, QColor(245, 166, 35, 0))
        painter.setBrush(QBrush(core_glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), inner_r * 0.65, inner_r * 0.65)

    # --- MAIN PAINT EVENT ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        self._draw_glossy_chassis(painter, rect)

        if self.height() < 260:
            self._paint_compact(painter, rect)
        else:
            self._paint_expanded(painter, rect)

    def _paint_compact(self, painter: QPainter, rect: QRectF):
        """Compact HUD layout matching image_b64c64.png."""
        amber = QColor(245, 166, 35)
        text_white = QColor(242, 242, 242)
        text_muted = QColor(150, 154, 162)

        # Top header: Glowing dot + CLAUDE // SYSTEM CORE
        painter.setBrush(QBrush(amber))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(24, 29), 3.5, 3.5)

        painter.setPen(amber)
        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.drawText(36, 33, "CLAUDE // SYSTEM CORE")

        # Middle row: SESSION LOAD + large percentage
        painter.setPen(text_muted)
        painter.setFont(QFont("Consolas", 10))
        painter.drawText(22, 82, "SESSION LOAD")

        session_val = self.usage_data["session"]
        painter.setPen(text_white)
        painter.setFont(QFont("Consolas", 22, QFont.Weight.Bold))
        painter.drawText(132, 84, f"{session_val:.1f}%")

        # Horizontal progress bar
        bar_rect = QRectF(22, 102, 225, 4)
        painter.setBrush(QBrush(QColor(255, 255, 255, 35)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bar_rect, 2, 2)

        fill_w = max(4.0, bar_rect.width() * min(session_val / 100.0, 1.0))
        painter.setBrush(QBrush(amber))
        painter.drawRoundedRect(QRectF(bar_rect.x(), bar_rect.y(), fill_w, bar_rect.height()), 2, 2)

        # Bottom row: Token count + LIVE indicator
        total_tok = self.usage_data["context_tokens"]
        painter.setPen(text_muted)
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(22, 123, f"{total_tok:,} TOKENS")

        painter.setPen(amber)
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        painter.drawText(220, 123, "LIVE")

        # Right side: Concentric Radar Core
        self._draw_reactor_core(painter, rect.right() - 62, rect.center().y() + 4, 42)

    def _paint_expanded(self, painter: QPainter, rect: QRectF):
        """Expanded HUD layout matching image_b64c08.jpg."""
        amber = QColor(245, 166, 35)
        text_white = QColor(242, 242, 242)
        text_muted = QColor(145, 150, 158)
        card_bg = QColor(255, 255, 255, 10)
        card_border = QColor(255, 255, 255, 24)

        # 1. Header
        painter.setPen(amber)
        painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        painter.drawText(22, 25, "ONLINE / MONITORING")

        self.collapse_rect = QRectF(rect.right() - 88, 12, 74, 20)
        painter.setPen(text_muted)
        painter.drawText(self.collapse_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "COLLAPSE  —")

        painter.setPen(text_white)
        painter.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
        painter.drawText(22, 48, "CLAUDE // SYSTEM CORE")

        # 2. Hero Radar + Current Session Hero Metric
        self._draw_reactor_core(painter, 76, 118, 44)

        painter.setPen(text_muted)
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(146, 98, "CURRENT SESSION")

        session_val = self.usage_data["session"]
        painter.setPen(text_white)
        painter.setFont(QFont("Consolas", 26, QFont.Weight.Bold))
        val_str = f"{session_val:.1f}"
        painter.drawText(146, 128, val_str)

        painter.setPen(amber)
        painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        painter.drawText(146 + len(val_str) * 19, 128, "%")

        # Status dot + NOMINAL / ELEVATED
        status_label = "NOMINAL" if session_val < 75 else "HIGH LOAD"
        painter.setBrush(QBrush(amber))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(150, 144), 3, 3)
        painter.setPen(amber)
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        painter.drawText(160, 148, status_label)

        # Mini equaliser bars on the right
        eq_heights = [6, 12, 8, 16, 10, 19, 13, 15, 7, 11]
        for i, h in enumerate(eq_heights):
            dyn_h = h * (0.75 + 0.25 * math.sin(self.pulse_phase + i))
            painter.fillRect(
                QRectF(rect.right() - 78 + i * 5.5, 142 - dyn_h, 2.5, dyn_h),
                QColor(245, 166, 35, 110),
            )

        # Divider line
        painter.setPen(QPen(card_border, 1))
        painter.drawLine(20, 174, int(rect.right() - 20), 174)

        # 3. Context Window Load Bar
        painter.setPen(text_muted)
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        painter.drawText(22, 196, "CONTEXT WINDOW LOAD")

        ctx_tok = self.usage_data["context_tokens"]
        ctx_max = self.usage_data["context_max"]
        painter.setPen(text_white)
        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.drawText(265, 196, f"{ctx_tok:,}")
        painter.setPen(text_muted)
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(332, 196, f"/ {ctx_max:,}")

        track = QRectF(22, 206, rect.width() - 44, 8)
        painter.setBrush(QBrush(QColor(0, 0, 0, 120)))
        painter.setPen(QPen(card_border, 1))
        painter.drawRect(track)

        fill_w = track.width() * min(ctx_tok / max(ctx_max, 1), 1.0)
        if fill_w > 0:
            painter.fillRect(QRectF(track.x() + 1, track.y() + 1, fill_w, track.height() - 2), amber)
            # Bright vertical cursor needle
            painter.fillRect(QRectF(track.x() + fill_w, track.y() - 3, 2, track.height() + 6), text_white)

        # Scale ticks (0, 50K, 100K, 150K, 200K)
        painter.setPen(QColor(110, 115, 122))
        painter.setFont(QFont("Consolas", 7))
        for idx, lbl in enumerate(["0", "50K", "100K", "150K", "200K"]):
            tx = track.x() + (track.width() * idx / 4.0) - (10 if idx > 0 else 0)
            painter.drawText(int(tx), 226, lbl)

        # 4. 2x2 Telemetry Cards Grid
        grid_top = 240
        card_w = (rect.width() - 52) / 2.0
        card_h = 74.0
        gap = 8.0

        cards = [
            ("INPUT", f"{self.usage_data['input_tokens']:,}", "TOKENS RECEIVED", False),
            ("OUTPUT", f"{self.usage_data['output_tokens']:,}", "TOKENS GENERATED", False),
            ("CACHE READ", f"{self.usage_data['cache_read']:,}", "TOKENS RECOVERED", False),
            ("WEEKLY USAGE", f"{self.usage_data['weekly']:.1f}%", "", True),
        ]

        for idx, (title, main_val, sub_lbl, has_bar) in enumerate(cards):
            col = idx % 2
            row = idx // 2
            cx = 22 + col * (card_w + gap)
            cy = grid_top + row * (card_h + gap)
            c_rect = QRectF(cx, cy, card_w, card_h)

            painter.setBrush(QBrush(card_bg))
            painter.setPen(QPen(card_border, 1))
            painter.drawRoundedRect(c_rect, 4, 4)

            painter.setPen(text_muted)
            painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
            painter.drawText(int(cx + 12), int(cy + 20), title)

            painter.setPen(text_white)
            painter.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            painter.drawText(int(cx + 12), int(cy + 44), main_val)

            if has_bar:
                w_bar = QRectF(cx + 12, cy + 56, card_w - 24, 3)
                painter.fillRect(w_bar, QColor(255, 255, 255, 30))
                w_fill = w_bar.width() * min(self.usage_data["weekly"] / 100.0, 1.0)
                painter.fillRect(QRectF(w_bar.x(), w_bar.y(), w_fill, 3), amber)
            else:
                painter.setPen(QColor(110, 115, 122))
                painter.setFont(QFont("Consolas", 6))
                painter.drawText(int(cx + 12), int(cy + 61), sub_lbl)

        # 5. Model / Reset Countdown / State Strip
        meta_y = 412
        painter.setPen(text_muted)
        painter.setFont(QFont("Consolas", 7))
        painter.drawText(22, meta_y, "MODEL")
        painter.drawText(225, meta_y, "RESET IN")
        painter.drawText(350, meta_y, "STATE")

        painter.setPen(text_white)
        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        painter.drawText(22, meta_y + 16, self.usage_data["model"])

        rem = self.usage_data["reset_time"] - datetime.now().astimezone()
        secs = max(int(rem.total_seconds()), 0)
        hrs, r_sec = divmod(secs, 3600)
        mins, s = divmod(r_sec, 60)
        painter.drawText(225, meta_y + 16, f"{hrs:02d}:{mins:02d}:{s:02d}")

        painter.setPen(amber)
        painter.drawText(350, meta_y + 16, "LIVE" if self.usage_data["is_live"] else "IDLE")

        # 6. Interactive Animation Mode Footer Bar
        painter.setPen(QPen(card_border, 1))
        painter.drawLine(20, 444, int(rect.right() - 20), 444)

        painter.setPen(text_muted)
        painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        painter.drawText(22, 469, "ANIMATION")

        self.mode_rects.clear()
        btn_x = 84
        for mode in ("ORBIT", "SCAN", "PULSE"):
            b_rect = QRectF(btn_x, 455, 42, 20)
            self.mode_rects[mode] = b_rect
            active = self.anim_mode == mode
            painter.setBrush(QBrush(amber if active else card_bg))
            painter.setPen(QPen(amber if active else card_border, 1))
            painter.drawRect(b_rect)

            painter.setPen(QColor(15, 15, 15) if active else text_muted)
            painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
            painter.drawText(b_rect, Qt.AlignmentFlag.AlignCenter, mode)
            btn_x += 44

        # Pause / Resume button on bottom right
        self.pause_rect = QRectF(rect.right() - 68, 455, 48, 20)
        painter.setBrush(QBrush(amber if self.anim_paused else card_bg))
        painter.setPen(QPen(amber if self.anim_paused else card_border, 1))
        painter.drawRect(self.pause_rect)
        painter.setPen(QColor(15, 15, 15) if self.anim_paused else text_muted)
        painter.drawText(
            self.pause_rect,
            Qt.AlignmentFlag.AlignCenter,
            "PLAY" if self.anim_paused else "PAUSE",
        )