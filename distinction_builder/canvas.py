"""An interactive canvas for building forms by direct manipulation.

Each form is a rounded box (:class:`FormItem`). A box is a *drawn distinction*:
its boundary is the mark, its interior is the space it holds. So the visual
grammar is the calculus's grammar —

* a box may hold a **body of text** (double-click to edit) — that makes it a
  note, the simplest content-bearing form;
* dragging one box onto another **places it inside** the target — containment,
  i.e. nesting distinctions.

:meth:`FormItem.to_form` reads a box (and everything nested in it) back into the
pure :mod:`laws_of_form` tree, so what you build on the canvas *is* a form.

The canvas itself (:class:`FormCanvas`) is a :class:`QGraphicsView`: double-click
empty space to create a form, drag to move/nest, Delete to remove.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QLineEdit,
    QStyleOptionGraphicsItem,
    QWidget,
)

# Geometry
PADDING = 14  # gap between a box's edge and its content
GAP = 8  # vertical gap between stacked children (and text ↔ children)
MIN_W = 96
MIN_H = 48
CORNER = 12  # rounded-corner radius
MAX_TEXT_W = 240  # text wraps beyond this width

# Palette — fill tints by nesting depth so containment reads at a glance.
_FILLS = ["#ffffff", "#eaf2fb", "#dfeaf6", "#d3ddec", "#c7d3e6"]
_BORDER = QColor("#3a3f4b")
_BORDER_SELECTED = QColor("#2f6fd6")
_TEXT = QColor("#1c1f26")
_PLACEHOLDER = QColor("#9aa0aa")


class FormItem(QGraphicsObject):
    """A rounded box: a distinction that may hold text and nested forms."""

    def __init__(self, text: str = "", parent: QGraphicsItem | None = None) -> None:
        # Attributes read by boundingRect()/paint() must exist *before* the C++
        # base is constructed — Qt calls those overrides during construction and
        # Shiboken swallows the AttributeError, silently breaking the item.
        self._text = text
        self._w = float(MIN_W)
        self._h = float(MIN_H)
        self._editor: tuple[QGraphicsProxyWidget, QLineEdit] | None = None
        super().__init__(parent)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._reflow()

    # -- geometry / painting -------------------------------------------------

    def boundingRect(self) -> QRectF:
        m = 1.0  # room for the pen
        return QRectF(-m, -m, self._w + 2 * m, self._h + 2 * m)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, self._w, self._h)
        path = QPainterPath()
        path.addRoundedRect(rect, CORNER, CORNER)

        painter.fillPath(path, QBrush(QColor(_FILLS[min(self._depth(), len(_FILLS) - 1)])))
        selected = self.isSelected()
        pen = QPen(_BORDER_SELECTED if selected else _BORDER, 2.0 if selected else 1.4)
        painter.setPen(pen)
        painter.drawPath(path)

        if self._editor is not None:
            return  # the inline editor is showing; don't paint text under it
        painter.setFont(_font())
        if self._text:
            painter.setPen(_TEXT)
            text_rect = QRectF(PADDING, PADDING, self._w - 2 * PADDING, self._text_size()[1])
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap),
                self._text,
            )
        elif not self._child_forms():
            painter.setPen(_PLACEHOLDER)
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "double-click")

    # -- layout --------------------------------------------------------------

    def _reflow(self) -> None:
        """Stack children under the text, size the box to fit, propagate up."""
        children = self._child_forms()
        text_w, text_h = self._text_size()

        y = float(PADDING)
        if self._text:
            y += text_h
            if children:
                y += GAP
        content_w = float(text_w)
        for child in children:
            child.setPos(PADDING, y)
            y += child._h + GAP
            content_w = max(content_w, child._w)
        if children:
            y -= GAP  # trailing gap

        new_w = max(PADDING + content_w + PADDING, MIN_W)
        new_h = max(y + PADDING, MIN_H)
        if new_w != self._w or new_h != self._h:
            self.prepareGeometryChange()
            self._w, self._h = new_w, new_h
        self.update()

        parent = self.parentItem()
        if isinstance(parent, FormItem):
            parent._reflow()

    def _child_forms(self) -> list["FormItem"]:
        kids = [c for c in self.childItems() if isinstance(c, FormItem)]
        kids.sort(key=lambda c: (c.pos().y(), c.pos().x()))
        return kids

    def _text_size(self) -> tuple[float, float]:
        if not self._text:
            return (0.0, 0.0)
        fm = QFontMetrics(_font())
        r = fm.boundingRect(
            QRect(0, 0, MAX_TEXT_W, 100000),
            int(Qt.TextFlag.TextWordWrap),
            self._text,
        )
        return (float(r.width()), float(r.height()))

    def _depth(self) -> int:
        depth, p = 0, self.parentItem()
        while isinstance(p, FormItem):
            depth += 1
            p = p.parentItem()
        return depth

    # -- text editing --------------------------------------------------------

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.begin_edit()
        event.accept()

    def begin_edit(self) -> None:
        """Show an inline editor over the text area."""
        if self._editor is not None:
            return
        editor = QLineEdit(self._text)
        editor.setFrame(False)
        editor.setPlaceholderText("text…")
        width = max(140, self._w - 2 * PADDING)
        editor.setFixedWidth(int(width))
        # Grow the box so the editor fits while typing.
        if self._w < width + 2 * PADDING:
            self.prepareGeometryChange()
            self._w = width + 2 * PADDING
            self.update()

        proxy = QGraphicsProxyWidget(self)
        proxy.setWidget(editor)
        proxy.setPos(PADDING, PADDING)
        self._editor = (proxy, editor)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        editor.editingFinished.connect(self._commit_edit)
        editor.selectAll()
        editor.setFocus(Qt.FocusReason.MouseFocusReason)

    def _commit_edit(self) -> None:
        if self._editor is None:
            return
        proxy, editor = self._editor
        self._editor = None  # guard against re-entry from focus-out
        editor.editingFinished.disconnect(self._commit_edit)
        self._text = editor.text().strip()
        proxy.setWidget(None)
        editor.deleteLater()
        if proxy.scene() is not None:
            proxy.scene().removeItem(proxy)
        proxy.deleteLater()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self._reflow()

    # -- dragging / containment ----------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.setZValue(1000.0)  # ride above others while dragging
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().mouseReleaseEvent(event)
        self._handle_drop()
        self.setZValue(0.0)

    def _handle_drop(self) -> None:
        """On release, nest into the form under our center, or detach to top."""
        scene = self.scene()
        if scene is None:
            return
        center = self.mapToScene(QRectF(0, 0, self._w, self._h).center())

        target: FormItem | None = None
        for item in scene.items(center):
            if item is self or not isinstance(item, FormItem):
                continue
            if self._is_ancestor_of(item):  # can't nest into our own descendant
                continue
            target = item
            break

        current_parent = self.parentItem() if isinstance(self.parentItem(), FormItem) else None
        if target is current_parent:
            if current_parent is not None:
                current_parent._reflow()  # snap back into place
            return
        if target is not None:
            self._reparent_into(target)
        else:
            self._detach_to_top()

    def _reparent_into(self, target: "FormItem") -> None:
        old_parent = self.parentItem()
        self.setParentItem(target)
        target._reflow()
        if isinstance(old_parent, FormItem):
            old_parent._reflow()

    def _detach_to_top(self) -> None:
        old_parent = self.parentItem()
        if old_parent is None:
            return  # already free; the drag already moved us
        scene_pos = self.scenePos()
        self.setParentItem(None)  # stays in the scene as a top-level item
        self.setPos(scene_pos)
        if isinstance(old_parent, FormItem):
            old_parent._reflow()

    def _is_ancestor_of(self, other: QGraphicsItem) -> bool:
        p = other.parentItem()
        while p is not None:
            if p is self:
                return True
            p = p.parentItem()
        return False

    # -- model bridge --------------------------------------------------------

    def to_form(self):
        """Read this box (and all nested forms) as a :mod:`laws_of_form` tree.

        A box is a distinction, so it becomes a ``Mark`` around the space of its
        text (if any) and its children — an empty box is the bare cross ``()``.
        """
        from laws_of_form import Mark, Space, Text

        parts: list = []
        if self._text:
            parts.append(Text(self._text))
        parts.extend(child.to_form() for child in self._child_forms())
        return Mark(Space(tuple(parts)))


class FormCanvas(QGraphicsView):
    """The drawing surface: create, move, nest, and delete forms."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        scene = QGraphicsScene(self)
        scene.setSceneRect(-2000, -2000, 4000, 4000)
        self.setScene(scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#f0f1f3"))
        self.centerOn(0, 0)

    # -- creation / deletion -------------------------------------------------

    def add_form(self, scene_pos: QPointF, text: str = "", edit: bool = False) -> FormItem:
        item = FormItem(text)
        self.scene().addItem(item)
        item.setPos(scene_pos - QPointF(item._w / 2, item._h / 2))
        item.setSelected(True)
        if edit:
            item.begin_edit()
        return item

    def top_level_forms(self) -> list[FormItem]:
        forms = [
            it
            for it in self.scene().items()
            if isinstance(it, FormItem) and not isinstance(it.parentItem(), FormItem)
        ]
        forms.sort(key=lambda it: (it.scenePos().y(), it.scenePos().x()))
        return forms

    def to_form(self):
        """The whole canvas as a :mod:`laws_of_form` space of its top forms."""
        from laws_of_form import Space

        return Space(tuple(it.to_form() for it in self.top_level_forms()))

    # -- events --------------------------------------------------------------

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        pos = event.position().toPoint()
        if self._form_under(self.itemAt(pos)) is not None:
            super().mouseDoubleClickEvent(event)  # let the form edit its text
            return
        self.add_form(self.mapToScene(pos), edit=True)
        event.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._delete_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt override)
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def _delete_selected(self) -> None:
        for item in list(self.scene().selectedItems()):
            if not isinstance(item, FormItem):
                continue
            parent = item.parentItem()
            self.scene().removeItem(item)  # removes its nested forms too
            if isinstance(parent, FormItem):
                parent._reflow()

    @staticmethod
    def _form_under(item: QGraphicsItem | None) -> FormItem | None:
        while item is not None:
            if isinstance(item, FormItem):
                return item
            item = item.parentItem()
        return None


def _font() -> QFont:
    font = QFont()
    font.setPointSize(11)
    return font
