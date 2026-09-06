import threading
import time

from AppKit import (
    NSColor,
    NSData,
    NSFont,
    NSImage,
    NSImageView,
    NSLineBreakByWordWrapping,
    NSMakeRect,
    NSTimer,
    NSURL,
    NSView,
)
from PyObjCTools import AppHelper

from ...features import nowplaying, sound
from . import widgets
from .constants import BTN_H, PAD

ARTWORK_SIZE = 90


def build(controller, w, h):
    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    inner_w = w - PAD * 2
    controller.np_checking = False
    controller.np_timer = None

    y = h - PAD - 20
    view.addSubview_(widgets.label(NSMakeRect(PAD, y, inner_w, 20), "Now Playing", bold=True))

    y -= 8 + 30
    hint = widgets.label(
        NSMakeRect(PAD, y, inner_w, 30),
        "Живое превью того, что уходит в MQTT/HA — обновляется само.",
    )
    hint.setTextColor_(NSColor.secondaryLabelColor())
    hint.setFont_(NSFont.systemFontOfSize_(11))
    hint.cell().setWraps_(True)
    hint.cell().setLineBreakMode_(NSLineBreakByWordWrapping)
    view.addSubview_(hint)

    y -= 14 + ARTWORK_SIZE
    artwork = NSImageView.alloc().initWithFrame_(NSMakeRect((w - ARTWORK_SIZE) / 2, y, ARTWORK_SIZE, ARTWORK_SIZE))
    controller.np_artwork_view = artwork
    view.addSubview_(artwork)

    y -= 8 + 18
    state_lbl = widgets.label(NSMakeRect(PAD, y, inner_w, 18), "Проверяю…", center=True)
    controller.np_state_label = state_lbl
    view.addSubview_(state_lbl)

    y -= 4 + 34
    title_lbl = widgets.label(NSMakeRect(PAD, y, inner_w, 34), "", center=True)
    title_lbl.cell().setWraps_(True)
    title_lbl.cell().setLineBreakMode_(NSLineBreakByWordWrapping)
    controller.np_title_label = title_lbl
    view.addSubview_(title_lbl)

    y -= 4 + 18
    artist_lbl = widgets.label(NSMakeRect(PAD, y, inner_w, 18), "", center=True)
    artist_lbl.setTextColor_(NSColor.secondaryLabelColor())
    artist_lbl.setFont_(NSFont.systemFontOfSize_(11))
    controller.np_artist_label = artist_lbl
    view.addSubview_(artist_lbl)

    # Real player controls — the same media keys HA/MQTT would trigger, so
    # clicking here is a genuine end-to-end test, not a mockup.
    y -= 20 + BTN_H
    ctrl_gap = 8
    ctrl_w = (inner_w - ctrl_gap * 2) / 3
    view.addSubview_(
        widgets.button(NSMakeRect(PAD, y, ctrl_w, BTN_H), "⏮", controller, "tapPrevious:")
    )
    view.addSubview_(
        widgets.button(NSMakeRect(PAD + ctrl_w + ctrl_gap, y, ctrl_w, BTN_H), "⏯", controller, "tapPlayPause:")
    )
    view.addSubview_(
        widgets.button(NSMakeRect(PAD + (ctrl_w + ctrl_gap) * 2, y, ctrl_w, BTN_H), "⏭", controller, "tapNext:")
    )

    return view


def tap_previous(controller, sender):
    sound.tap_previous()
    _refresh_after_control(controller)


def tap_play_pause(controller, sender):
    sound.tap_play_pause()
    _refresh_after_control(controller)


def tap_next(controller, sender):
    sound.tap_next()
    _refresh_after_control(controller)


def _refresh_after_control(controller):
    # Media keys act instantly, but the target app's metadata/tab needs a
    # beat to update — same reasoning as poll()'s own cadence, just short
    # enough to feel responsive for a manual click. The regular auto-refresh
    # tick (every CHECK_INTERVAL) would catch it anyway; this just avoids
    # waiting up to a full interval after a button click specifically.
    def worker():
        time.sleep(0.8)
        AppHelper.callAfter(_check_now_playing, controller)

    threading.Thread(target=worker, daemon=True).start()


def start_auto_refresh(controller):
    # Tab reads like a live player, not a one-shot test — it polls on its
    # own at the same cadence poll() uses for real, so what's on screen
    # always matches what would go out over MQTT. No manual "check" button:
    # since this always runs, one would just duplicate what's already
    # happening a second later on its own.
    stop_auto_refresh(controller)
    _check_now_playing(controller)
    controller.np_timer = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
        nowplaying.CHECK_INTERVAL, True, lambda timer: _check_now_playing(controller)
    )


def stop_auto_refresh(controller):
    timer = getattr(controller, "np_timer", None)
    if timer is not None:
        timer.invalidate()
        controller.np_timer = None


def _check_now_playing(controller):
    if controller.np_checking:
        return
    controller.np_checking = True

    def worker():
        # current_track() — the same fast, short-circuiting path poll() uses
        # (~0.1s: stops at the first engine that answers, normally
        # MediaRemote). The full, all-engines diagnose() used to run here
        # instead and made this tick take as long as its slowest engine
        # (up to CALL_TIMEOUT, e.g. Safari without Automation permission) —
        # that's what made a 1s auto-refresh only visibly update every ~2s.
        info = nowplaying.current_track()
        AppHelper.callAfter(_apply_track, controller, info)

    threading.Thread(target=worker, daemon=True).start()


def _apply_track(controller, info):
    controller.np_checking = False

    if info is None:
        controller.np_state_label.setStringValue_("⏸ Ничего не играет")
        controller.np_title_label.setStringValue_("")
        controller.np_artist_label.setStringValue_("")
        controller.np_artwork_view.setImage_(None)
        return

    playing = info.get("playing", True)
    controller.np_state_label.setStringValue_("▶ Воспроизводится" if playing else "⏸ На паузе")
    controller.np_title_label.setStringValue_(info.get("title") or "")
    controller.np_artist_label.setStringValue_(info.get("artist") or "")

    artwork_url = info.get("artwork") or ""
    if artwork_url:
        _load_artwork(controller, artwork_url)
    else:
        controller.np_artwork_view.setImage_(None)


def _load_artwork(controller, url):
    def worker():
        try:
            data = NSData.dataWithContentsOfURL_(NSURL.URLWithString_(url))
            image = NSImage.alloc().initWithData_(data) if data else None
        except Exception:
            image = None
        AppHelper.callAfter(_set_artwork, controller, image)

    threading.Thread(target=worker, daemon=True).start()


def _set_artwork(controller, image):
    controller.np_artwork_view.setImage_(image)
