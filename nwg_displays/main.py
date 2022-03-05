#!/usr/bin/env python

"""
https://gist.github.com/KurtJacobson/57679e5036dc78e6a7a3ba5e0155dad1
"""

import os
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

dir_name = os.path.dirname(__file__)

from nwg_displays.tools import *

# higher values make movement more performant
# lower values make movement smoother
SENSITIVITY = 1
view_scale = 0.1
snap_threshold = 10
snap_threshold_scaled = None
update_form = True

EvMask = Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON1_MOTION_MASK

outputs = {}
fixed = Gtk.Fixed()

selected_output_button = None

offset_x = 0
offset_y = 0
px = 0
py = 0
max_x = 0
max_y = 0

# Glade form fields
form_name = None
form_description = None
form_active = None
form_dpms = None
form_adaptive_sync = None
form_view_scale = None
form_x = None
form_y = None
form_width = None
form_height = None
form_scale = None
form_scale_filter = None
form_refresh = None
form_modes = None
form_transform = None
form_close = None
form_apply = None

display_buttons = []


def on_button_press_event(widget, event):
    if event.button == 1:
        for db in display_buttons:
            if db.name == widget.name:
                db.select()
            else:
                db.unselect()

        p = widget.get_parent()
        # offset == distance of parent widget from edge of screen ...
        global offset_x, offset_y
        offset_x, offset_y = p.get_window().get_position()
        # plus distance from pointer to edge of widget
        offset_x += event.x
        offset_y += event.y
        # max_x, max_y both relative to the parent
        # note that we're rounding down now so that these max values don't get
        # rounded upward later and push the widget off the edge of its parent.
        global max_x, max_y
        max_x = round_down_to_multiple(p.get_allocation().width - widget.get_allocation().width, SENSITIVITY)
        max_y = round_down_to_multiple(p.get_allocation().height - widget.get_allocation().height, SENSITIVITY)

        update_form_from_widget(selected_output_button)


def on_motion_notify_event(widget, event):
    # x_root,x_root relative to screen
    # x,y relative to parent (fixed widget)
    # px,py stores previous values of x,y

    global px, py
    global offset_x, offset_y

    # get starting values for x,y
    x = event.x_root - offset_x
    y = event.y_root - offset_y
    # make sure the potential coordinates x,y:
    #   1) will not push any part of the widget outside of its parent container
    #   2) is a multiple of SENSITIVITY
    x = round_to_nearest_multiple(max_val(min_val(x, max_x), 0), SENSITIVITY)
    y = round_to_nearest_multiple(max_val(min_val(y, max_y), 0), SENSITIVITY)

    if x != px or y != py:
        px = x
        py = y
        snap_x, snap_y = [0], [0]
        for db in display_buttons:
            if db.name == widget.name:
                continue

            val = round(db.x * view_scale)
            if val not in snap_x:
                snap_x.append(val)

            val = round((db.x + db.width) * view_scale)
            if val not in snap_x:
                snap_x.append(val)

            val = round(db.y * view_scale)
            if val not in snap_y:
                snap_y.append(val)

            val = round((db.y + db.height) * view_scale)
            if val not in snap_y:
                snap_y.append(val)

        snap_h, snap_v = None, None
        for value in snap_x:
            if abs(x - value) < snap_threshold_scaled:
                snap_h = value
                break

        for value in snap_x:
            w = round(widget.width * view_scale)
            if abs(w + x - value) < snap_threshold_scaled:
                snap_h = value - w
                break

        for value in snap_y:
            if abs(y - value) < snap_threshold_scaled:
                snap_v = value
                break

        for value in snap_y:
            h = round(widget.height * view_scale)
            if abs(h + y - value) < snap_threshold_scaled:
                snap_v = value - h
                break

        if snap_h is None and snap_v is None:
            fixed.move(widget, x, y)
            widget.x = round(x / view_scale)
            widget.y = round(y / view_scale)
        else:

            if snap_h is not None and snap_v is not None:
                fixed.move(widget, snap_h, snap_v)
                widget.x = round(snap_h / view_scale)
                widget.y = round(snap_v / view_scale)

            elif snap_h is not None:
                fixed.move(widget, snap_h, y)
                widget.x = round(snap_h / view_scale)
                widget.y = round(y / view_scale)

            elif snap_v is not None:
                fixed.move(widget, x, snap_v)
                widget.x = round(x / view_scale)
                widget.y = round(snap_v / view_scale)

    update_form_from_widget(widget)


def update_form_from_widget(widget, *args):
    if update_form:
        print("Updating form")
        form_name.set_text(widget.name)
        form_description.set_text(widget.description)
        form_active.set_active(widget.active)
        form_dpms.set_active(widget.dpms)
        form_adaptive_sync.set_active(widget.adaptive_sync)
        form_view_scale.set_value(view_scale)  # not really from the widget, but from the global value
        form_x.set_value(widget.x)
        form_y.set_value(widget.y)
        form_width.set_value(widget.width)
        form_height.set_value(widget.height)
        form_scale.set_value(widget.scale)
        form_scale_filter.set_active_id(widget.scale_filter)
        form_refresh.set_value(widget.refresh)

        form_modes.remove_all()
        active = ""
        for mode in widget.modes:
            m = "{}x{}@{}Hz".format(mode["width"], mode["height"], mode["refresh"] / 1000)
            form_modes.append(m, m)
            # This is just to set active_id
            if "90" in widget.transform or "270" in widget.transform:
                if mode["width"] == widget.height and mode["height"] == widget.width and mode[
                        "refresh"] / 1000 == widget.refresh:
                    active = m
            else:
                if mode["width"] == widget.width and mode["height"] == widget.height and mode[
                        "refresh"] / 1000 == widget.refresh:
                    active = m
        if active:
            form_modes.set_active_id(active)

        form_transform.set_active_id(widget.transform)


class DisplayButton(Gtk.Button):
    def __init__(self, name, description, x, y, width, height, transform, scale, scale_filter, refresh, modes, active,
                 dpms, adaptive_sync_status, focused):
        super().__init__()
        # Output properties
        self.name = name
        self.description = description
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.transform = transform
        self.scale = scale
        self.scale_filter = scale_filter
        self.refresh = refresh
        self.modes = modes
        self.active = active
        self.dpms = dpms
        self.adaptive_sync = adaptive_sync_status == "enabled"  # converts "enabled | disabled" to bool
        self.focused = focused

        # Button properties
        self.selected = False
        self.set_can_focus(False)
        self.set_events(EvMask)
        self.connect("button_press_event", on_button_press_event)
        self.connect("motion_notify_event", on_motion_notify_event)
        self.set_always_show_image(True)
        self.set_label(self.name)
        self.set_size_request(round(self.width * view_scale), round(self.height * view_scale))
        self.set_property("name", "output")

        self.show()

    def select(self):
        self.selected = True
        self.set_property("name", "selected-output")
        global selected_output_button
        selected_output_button = self

    def unselect(self):
        self.set_property("name", "output")

    def rescale(self):
        self.set_size_request(round(self.width * view_scale), round(self.height * view_scale))


def update_widgets_from_form(*args, give_back=True):
    if selected_output_button:  # at first display_buttons are not yet instantiated
        global view_scale
        view_scale = form_view_scale.get_value()

        global snap_threshold, snap_threshold_scaled
        snap_threshold_scaled = round(snap_threshold * view_scale * 10)

        transform = form_transform.get_active_id()
        if orientation_changed(transform, selected_output_button.transform):
            selected_output_button.width, selected_output_button.height = selected_output_button.height, selected_output_button.width
            selected_output_button.transform = transform

        # On scale changed
        for b in display_buttons:
            b.rescale()
            fixed.move(b, b.x * view_scale, b.y * view_scale)

    global update_form
    update_form = give_back


def orientation_changed(transform, transform_old):
    return (is_rotated(transform) and not is_rotated(transform_old)) or (
            is_rotated(transform_old) and not is_rotated(transform))


def is_rotated(transform):
    return "90" in transform or "270" in transform


def main():
    global snap_threshold, snap_threshold_scaled
    snap_threshold_scaled = snap_threshold

    builder = Gtk.Builder()
    builder.add_from_file("main.glade")

    window = builder.get_object("window")
    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    try:
        file = os.path.join(dir_name, "style.css")
        provider.load_from_path(file)
    except:
        sys.stderr.write("ERROR: {} file not found, using GTK styling\n".format(os.path.join(dir_name, "style.css")))

    window.connect('destroy', Gtk.main_quit)

    global form_name
    form_name = builder.get_object("name")

    global form_description
    form_description = builder.get_object("description")

    global form_active
    form_active = builder.get_object("active")

    global form_dpms
    form_dpms = builder.get_object("dpms")

    global form_adaptive_sync
    form_adaptive_sync = builder.get_object("adaptive-sync")

    global form_view_scale
    form_view_scale = builder.get_object("view-scale")
    adj = Gtk.Adjustment(lower=0.1, upper=0.6, step_increment=0.05, page_increment=0.1, page_size=0.1)
    form_view_scale.configure(adj, 1, 2)
    form_view_scale.connect("changed", update_widgets_from_form, False)

    global form_x
    form_x = builder.get_object("x")
    adj = Gtk.Adjustment(lower=0, upper=60000, step_increment=1, page_increment=10, page_size=1)
    form_x.configure(adj, 1, 0)

    global form_y
    form_y = builder.get_object("y")
    adj = Gtk.Adjustment(lower=0, upper=40000, step_increment=1, page_increment=10, page_size=1)
    form_y.configure(adj, 1, 0)

    global form_width
    form_width = builder.get_object("width")
    adj = Gtk.Adjustment(lower=0, upper=7680, step_increment=1, page_increment=10, page_size=1)
    form_width.configure(adj, 1, 0)

    global form_height
    form_height = builder.get_object("height")
    adj = Gtk.Adjustment(lower=0, upper=4320, step_increment=1, page_increment=10, page_size=1)
    form_height.configure(adj, 1, 0)

    global form_scale
    form_scale = builder.get_object("scale")
    adj = Gtk.Adjustment(lower=0.1, upper=1000, step_increment=0.1, page_increment=10, page_size=1)
    form_scale.configure(adj, 0.1, 1)

    global form_scale_filter
    form_scale_filter = builder.get_object("scale-filter")

    global form_refresh
    form_refresh = builder.get_object("refresh")
    adj = Gtk.Adjustment(lower=1, upper=1200, step_increment=1, page_increment=10, page_size=1)
    form_refresh.configure(adj, 1, 3)

    global form_modes
    form_modes = builder.get_object("modes")

    global form_transform
    form_transform = builder.get_object("transform")
    form_transform.connect("changed", update_widgets_from_form)

    global form_close
    form_close = builder.get_object("close")
    form_close.connect("clicked", Gtk.main_quit)

    global form_apply
    form_apply = builder.get_object("apply")

    wrapper = builder.get_object("wrapper")
    wrapper.set_property("name", "wrapper")

    global fixed
    fixed = builder.get_object("fixed")

    global outputs
    outputs = list_outputs()
    global display_buttons
    for key in outputs:
        item = outputs[key]
        b = DisplayButton(key, item["description"], item["x"], item["y"], round(item["width"]), round(item["height"]),
                          item["transform"], item["scale"], item["scale_filter"], item["refresh"], item["modes"],
                          item["active"], item["dpms"], item["adaptive_sync_status"], item["focused"])
        display_buttons.append(b)

        fixed.put(b, round(item["x"] * view_scale), round(item["y"] * view_scale))

    if display_buttons:
        update_form_from_widget(display_buttons[0])
        display_buttons[0].select()

    window.show_all()
    Gtk.main()


if __name__ == '__main__':
    sys.exit(main())
