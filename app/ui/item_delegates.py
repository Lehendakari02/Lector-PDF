"""How the rows of the result lists are painted.

The lists keep their plain text (screen readers and the tests read it); these
painters only make each row easier to read at a glance.
"""

from collections.abc import Callable

from PySide6.QtCore import QModelIndex, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from app.core.search import SearchHit
from app.ui import icons, theme
from app.ui.features import Feature, translate

PADDING = 10


def _paint_row_background(painter: QPainter, option: QStyleOptionViewItem) -> None:
    c = theme.colours()
    selected = bool(option.state & QStyle.StateFlag.State_Selected)
    hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
    if selected or hovered:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(c.accent_soft if selected else c.hover))
        painter.drawRoundedRect(QRectF(option.rect).adjusted(2, 1, -2, -1), 7, 7)


def _font(base: QFont, delta: float = 0, bold: bool = False) -> QFont:
    font = QFont(base)
    font.setPointSizeF(base.pointSizeF() + delta)
    if bold:
        font.setWeight(QFont.Weight.DemiBold)
    return font


class FeatureDelegate(QStyledItemDelegate):
    """A function in the finder: icon, name, what it does and its mode."""

    ICON_BOX = 38

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        metrics = QFontMetrics(option.font)
        return QSize(200, max(self.ICON_BOX, 2 * metrics.height() + 4) + 2 * 8)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        feature = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(feature, Feature):
            super().paint(painter, option, index)
            return
        c = theme.colours()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _paint_row_background(painter, option)
        row = option.rect.adjusted(PADDING + 2, 0, -PADDING - 2, 0)

        box = QRect(row.left(), row.center().y() - self.ICON_BOX // 2, self.ICON_BOX, self.ICON_BOX)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(c.window))
        painter.drawRoundedRect(QRectF(box), 9, 9)
        if icons.has_icon(feature.id):
            icons.icon(feature.id, icons.ACCENT).paint(painter, box.adjusted(8, 8, -8, -8))

        # The mode, in a small pill on the right.
        small = _font(option.font, -1.5, bold=True)
        mode = translate(feature.mode.value)
        mode_width = QFontMetrics(small).horizontalAdvance(mode) + 18
        pill = QRect(row.right() - mode_width, row.center().y() - 11, mode_width, 22)
        painter.setBrush(QColor(c.window))
        painter.drawRoundedRect(QRectF(pill), 11, 11)
        painter.setFont(small)
        painter.setPen(QColor(c.muted))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, mode)

        text = QRect(box.right() + 12, row.top(), pill.left() - box.right() - 24, row.height())
        name_font = _font(option.font, 0.5, bold=True)
        name_metrics = QFontMetrics(name_font)
        detail_font = _font(option.font, -1)
        detail_metrics = QFontMetrics(detail_font)
        top = text.center().y() - (name_metrics.height() + detail_metrics.height() + 2) // 2
        painter.setFont(name_font)
        painter.setPen(QColor(c.text))
        painter.drawText(
            QRect(text.left(), top, text.width(), name_metrics.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            name_metrics.elidedText(
                translate(feature.name), Qt.TextElideMode.ElideRight, text.width()
            ),
        )
        painter.setFont(detail_font)
        painter.setPen(QColor(c.muted))
        painter.drawText(
            QRect(
                text.left(), top + name_metrics.height() + 2, text.width(), detail_metrics.height()
            ),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            detail_metrics.elidedText(
                translate(feature.description), Qt.TextElideMode.ElideRight, text.width()
            ),
        )
        painter.restore()


class SearchHitDelegate(QStyledItemDelegate):
    """A search result: the page, and the sentence with the found word marked."""

    def __init__(self, hit_of_row: Callable[[int], SearchHit | None], before_length: int, parent):
        super().__init__(parent)
        self._hit_of_row = hit_of_row
        self._before_length = before_length
        self.page_label = "Pág. {0}"

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        metrics = QFontMetrics(option.font)
        return QSize(200, 2 * metrics.height() + 18)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        hit = self._hit_of_row(index.row())
        if hit is None:
            super().paint(painter, option, index)
            return
        c = theme.colours()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _paint_row_background(painter, option)
        row = option.rect.adjusted(PADDING + 2, 7, -PADDING - 2, -7)

        small = _font(option.font, -1.5, bold=True)
        small_metrics = QFontMetrics(small)
        painter.setFont(small)
        painter.setPen(QColor(c.accent))
        painter.drawText(
            QRect(row.left(), row.top(), row.width(), small_metrics.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.page_label.format(hit.page + 1),
        )

        before = hit.before
        if len(before) > self._before_length:
            before = before[-self._before_length :].partition(" ")[2]
        normal = QFont(option.font)
        bold = _font(option.font, 0, bold=True)
        normal_metrics, bold_metrics = QFontMetrics(normal), QFontMetrics(bold)
        line = QRect(
            row.left(),
            row.bottom() - normal_metrics.height() + 1,
            row.width(),
            normal_metrics.height(),
        )
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        x = line.left()
        painter.setFont(normal)
        painter.setPen(QColor(c.text))
        painter.drawText(QRect(x, line.top(), line.right() - x, line.height()), flags, before)
        x += normal_metrics.horizontalAdvance(before)

        match_width = bold_metrics.horizontalAdvance(hit.match)
        mark = QRectF(x - 2, line.top() - 1, match_width + 4, line.height() + 2)
        mark = mark.intersected(QRectF(line).adjusted(-2, -2, 0, 2))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.MARKER))
        painter.drawRoundedRect(mark, 3, 3)
        painter.setFont(bold)
        painter.setPen(QColor("#1b1d23"))  # always dark: it sits on the yellow mark
        room = max(0, line.right() - x)
        painter.drawText(
            QRect(x, line.top(), room, line.height()),
            flags,
            bold_metrics.elidedText(hit.match, Qt.TextElideMode.ElideRight, room),
        )
        x += match_width

        room = line.right() - x
        if room > 0:
            painter.setFont(normal)
            painter.setPen(QColor(c.text))
            painter.drawText(
                QRect(x, line.top(), room, line.height()),
                flags,
                normal_metrics.elidedText(hit.after, Qt.TextElideMode.ElideRight, room),
            )
        painter.restore()
