# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The Deep Dive cards gliding to their new places when a deck or period change shows or
hides charts: the cards that stay slide, the ones that go fade out where they were, the new
ones fade in where they come.

Everything is drawn from pictures taken from the window itself (so the window's background
and the see-through cards come out exactly as on screen): the view before, the view after,
and the view's background alone (the cards hidden for an instant). An opaque overlay draws
the background, then each card's picture at its place of the moment. No chart is painted
while it runs (moving the cards themselves repainted every chart on every frame). The
charts already hold their new data: each card's old picture fades into its new one."""

from aqt.qt import (
    QEasingCurve, QGraphicsOpacityEffect, QPainter, QPoint, QRect, QRectF, QVariantAnimation, QWidget, Qt,
)

from ....logic.logger import log_swallowed

DURATION_MS = 280
_FADE_OUT_END = 0.45   # the cards that go are gone by then
_FADE_IN_START = 0.35  # the new cards come in from then


def grab_view(viewport):
    """What the viewport shows now, as the window draws it (None if it cannot)."""
    try:
        if viewport is None or not viewport.isVisible() or viewport.width() < 10 or viewport.height() < 10:
            return None
        win = viewport.window()
        top_left = viewport.mapTo(win, QPoint(0, 0))
        return win.grab(QRect(top_left, viewport.size()))
    except Exception:
        log_swallowed()
        return None


def card_rects(viewport, cards):
    """{card: its rect in the viewport} of the shown cards."""
    out = {}
    for w in cards:
        try:
            if w is not None and w.isVisible():
                out[w] = QRect(w.mapTo(viewport, QPoint(0, 0)), w.size())
        except RuntimeError:
            pass
    return out


def visible_change(viewport, old_rects, new_rects):
    """Whether a card moves, comes or goes inside the view (a change below the fold is not
    seen: there the charts animate their data as usual)."""
    try:
        view = QRect(QPoint(0, 0), viewport.size())
    except RuntimeError:
        return False
    for w in set(old_rects) | set(new_rects):
        old = old_rects.get(w)
        new = new_rects.get(w)
        if old == new:
            continue
        if (old is not None and old.intersects(view)) or (new is not None and new.intersects(view)):
            return True
    return False


def moves_in_view(viewport, old_rects, new_rects):
    """Whether a card that stays shown moves or changes size inside the view."""
    try:
        view = QRect(QPoint(0, 0), viewport.size())
    except RuntimeError:
        return False
    for w, old in old_rects.items():
        new = new_rects.get(w)
        if new is None or new == old:
            continue
        if old.intersects(view) or new.intersects(view):
            return True
    return False


class _FadeOut(QWidget):
    """The picture of a card that went, fading out where it was (over the live view)."""

    def __init__(self, viewport, picture, rect):
        super().__init__(viewport)
        self._pic = picture
        self._opacity = 1.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(rect)
        anim = QVariantAnimation(self)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setDuration(int(DURATION_MS * _FADE_OUT_END * 1.6))
        anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))
        anim.valueChanged.connect(self._on_value)
        anim.finished.connect(self.deleteLater)
        self._anim = anim

    def _on_value(self, value):
        self._opacity = float(value)
        self.update()

    def start(self):
        self.show()
        self.raise_()
        self._anim.start()

    def paintEvent(self, _event):
        p = QPainter(self)
        try:
            p.setOpacity(max(0.0, self._opacity))
            p.drawPixmap(self.rect(), self._pic)
        finally:
            p.end()


def fade_out_gone(viewport, old_view, old_rects, new_rects):
    """The cards that went (in old_rects, not in new_rects) fade out where they were."""
    try:
        view = QRect(QPoint(0, 0), viewport.size())
        for w, r in old_rects.items():
            if w in new_rects:
                continue
            seen = view.intersected(r)
            if seen.isEmpty():
                continue
            pic = old_view.copy(_part(old_view, seen).toRect())
            pic.setDevicePixelRatio(old_view.devicePixelRatio())
            _FadeOut(viewport, pic, seen).start()
    except Exception:
        log_swallowed()


def _background(viewport, cards):
    """The view without its cards (each one hidden for the picture by an opacity effect at
    0, which Qt skips; nothing moves)."""
    muted = []
    for w in cards:
        try:
            if w.graphicsEffect() is None:
                eff = QGraphicsOpacityEffect(w)
                eff.setOpacity(0.0)
                w.setGraphicsEffect(eff)
                muted.append(w)
        except RuntimeError:
            pass
    try:
        return grab_view(viewport)
    finally:
        for w in muted:
            try:
                w.setGraphicsEffect(None)
            except RuntimeError:
                pass


def _lerp(a, b, t):
    return QRectF(
        a.x() + (b.x() - a.x()) * t,
        a.y() + (b.y() - a.y()) * t,
        a.width() + (b.width() - a.width()) * t,
        a.height() + (b.height() - a.height()) * t,
    )


def _part(pm, rect):
    """The part of the picture pm (of the whole view) under rect (view coordinates)."""
    dpr = pm.devicePixelRatio() or 1.0
    return QRectF(rect.x() * dpr, rect.y() * dpr, rect.width() * dpr, rect.height() * dpr)


def _seen(view, r):
    """The part of r (view coordinates) in view, and the same part in r's own coordinates
    (None when nothing of r is in view)."""
    seen = view.intersected(r)
    if seen.isEmpty():
        return None, None
    return seen, QRectF(seen.translated(-r.topLeft()))


def _piece_at(at, r, local):
    """Where the part local (in r's coordinates) of a card at r is drawn when the card is
    drawn at at (r scaled and moved)."""
    kx = at.width() / max(1.0, float(r.width()))
    ky = at.height() / max(1.0, float(r.height()))
    return QRectF(at.x() + local.x() * kx, at.y() + local.y() * ky, local.width() * kx, local.height() * ky)


def _draw_card(p, view, pm, r, at, opacity):
    """The visible part of the card at r in the picture pm, drawn where the card is at at
    (a card cut by the view's edge is drawn as far as it was seen)."""
    if opacity <= 0.0:
        return
    seen, local = _seen(view, r)
    if seen is None:
        return
    p.setOpacity(min(1.0, opacity))
    p.drawPixmap(_piece_at(at, r, local), pm, _part(pm, seen))


class _Glide(QWidget):
    def __init__(self, viewport, old_view, new_view, back, old_rects, new_rects, on_done, duration):
        super().__init__(viewport)
        self._old_view, self._new_view, self._back = old_view, new_view, back
        self._moves, self._gone, self._come = [], [], []
        for w, r_new in new_rects.items():
            r_old = old_rects.get(w)
            if r_old is None:
                self._come.append(r_new)
            else:
                self._moves.append((r_old, r_new))
        for w, r_old in old_rects.items():
            if w not in new_rects:
                self._gone.append(r_old)
        self._on_done = on_done
        self._t = 0.0
        self._done = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # It covers the whole view with opaque pictures: nothing under it is painted.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setGeometry(viewport.rect())
        self._ease = QEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(int(duration))
        self._anim.valueChanged.connect(self._on_value)
        self._anim.finished.connect(self.finish)

    def start(self):
        self.show()
        self.raise_()
        self._anim.start()

    def _on_value(self, value):
        self._t = float(value)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            t = max(0.0, min(1.0, self._t))
            e = self._ease.valueForProgress(t)
            p.drawPixmap(self.rect(), self._back)
            # Going: fade out (and shrink a little) where they were.
            view = QRect(0, 0, self.width(), self.height())
            out = 1.0 - min(1.0, t / _FADE_OUT_END)
            if out > 0.0:
                for r in self._gone:
                    k = 0.04 * (1.0 - out)
                    target = QRectF(r).adjusted(r.width() * k, r.height() * k, -r.width() * k, -r.height() * k)
                    _draw_card(p, view, self._old_view, r, target, out)
            # Staying: slide from the old place to the new one, the old picture (the old
            # deck's data) fading into the new one.
            for r_old, r_new in self._moves:
                at = _lerp(QRectF(r_old), QRectF(r_new), e)
                # The old picture (old data) fading into the new one as it slides. A card cut
                # by the view's edge fades too: each picture as far as it was seen, the old one
                # kept under the new one where the new one covers it, faded out elsewhere.
                _seen_old, local_old = _seen(view, r_old)
                _seen_new, local_new = _seen(view, r_new)
                if local_old is not None:
                    covered = False
                    if local_new is not None:
                        kx = r_new.width() / max(1.0, float(r_old.width()))
                        ky = r_new.height() / max(1.0, float(r_old.height()))
                        mapped = QRectF(local_old.x() * kx, local_old.y() * ky, local_old.width() * kx, local_old.height() * ky)
                        covered = local_new.adjusted(-1, -1, 1, 1).contains(mapped)
                    _draw_card(p, view, self._old_view, r_old, at, 1.0 if covered else 1.0 - e)
                _draw_card(p, view, self._new_view, r_new, at, e if local_old is not None else 1.0)
            # Coming: fade in (and grow a little) where they come.
            come = max(0.0, (t - _FADE_IN_START) / (1.0 - _FADE_IN_START))
            if come > 0.0:
                for r in self._come:
                    k = 0.04 * (1.0 - come)
                    target = QRectF(r).adjusted(r.width() * k, r.height() * k, -r.width() * k, -r.height() * k)
                    _draw_card(p, view, self._new_view, r, target, come)
        finally:
            p.end()

    def finish(self):
        if self._done:
            return
        self._done = True
        try:
            self._anim.stop()
        except RuntimeError:
            pass
        try:
            self.hide()
            self.deleteLater()
        except RuntimeError:
            pass
        cb, self._on_done = self._on_done, None
        if cb is not None:
            try:
                cb()
            except Exception:
                log_swallowed()


def glide(viewport, old_view, old_rects, cards, on_done, duration=DURATION_MS):
    """Glide the cards from old_rects (taken with old_view, before they moved) to where they
    are now, then on_done(). Runs on_done at once (and returns None) when it cannot."""
    try:
        new_view = grab_view(viewport) if old_view is not None else None
        new_rects = card_rects(viewport, cards)
        back = _background(viewport, list(new_rects)) if new_view is not None else None
        if old_view is None or new_view is None or back is None or old_view.size() != new_view.size():
            on_done()
            return None
        g = _Glide(viewport, old_view, new_view, back, old_rects, new_rects, on_done, duration)
    except Exception:
        log_swallowed()
        on_done()
        return None
    g.start()
    return g
