from .controller import SettingsController


def show(cfg, on_save, on_toggle_icon):
    controller = SettingsController.alloc().initWithConfigAndCallback_((cfg, on_save, on_toggle_icon))
    controller.show()
    return controller
