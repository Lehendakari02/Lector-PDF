"""Small pictures of the shapes, drawn the way the page will have them."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

from app.core import drawing
from app.ui import theme

SIZE = 24


def _head(start: QPointF, end: QPointF) -> QPolygonF:
    dx, dy = end.x() - start.x(), end.y() - start.y()
    length = max((dx * dx + dy * dy) ** 0.5, 0.01)
    ux, uy = dx / length, dy / length
    back = QPointF(end.x() - ux * 5, end.y() - uy * 5)
    return QPolygonF(
        [
            QPointF(back.x() - uy * 3, back.y() + ux * 3),
            end,
            QPointF(back.x() + uy * 3, back.y() - ux * 3),
        ]
    )


def shape_icon(kind: str) -> QIcon:
    """The shape, in the colour of the text of the program."""
    icon = QIcon()
    for scale in (1, 2):
        pixmap = QPixmap(SIZE * scale, SIZE * scale)
        pixmap.setDevicePixelRatio(scale)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(theme.colours().text), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if kind in drawing.FRAMED_SHAPES:
            start, end = (4.0, 5.0), (20.0, 19.0)
            if kind == drawing.BRACE:
                start, end = (8.0, 3.0), (15.0, 21.0)
        elif kind == drawing.ELBOW:
            start, end = (3.0, 6.0), (18.0, 20.0)
        else:
            start, end = (3.0, 19.0), (21.0, 5.0)
        points = [QPointF(x, y) for x, y in drawing.shape_points(kind, start, end)]
        if kind == drawing.BOX:
            painter.drawRect(QRectF(points[0], points[2]))
        elif kind == drawing.OVAL:
            painter.drawEllipse(QRectF(points[0], points[2]))
        elif kind in (drawing.TRIANGLE, drawing.RHOMBUS):
            painter.drawPolygon(QPolygonF(points))
        else:
            painter.drawPolyline(QPolygonF(points))
        if kind in (drawing.ARROW, drawing.DOUBLE_ARROW, drawing.ELBOW):
            painter.drawPolyline(_head(points[-2], points[-1]))
        if kind == drawing.DOUBLE_ARROW:
            painter.drawPolyline(_head(points[1], points[0]))
        painter.end()
        icon.addPixmap(pixmap)
    return icon
