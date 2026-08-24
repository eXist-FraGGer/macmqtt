from ServiceManagement import SMAppService

# SMAppService.Status: 0 notRegistered, 1 enabled, 2 requiresApproval, 3 notFound.
SM_STATUS_ENABLED = 1


def launch_at_login_enabled():
    return SMAppService.mainAppService().status() == SM_STATUS_ENABLED


def set_launch_at_login(enabled):
    service = SMAppService.mainAppService()
    if enabled:
        service.registerAndReturnError_(None)
    else:
        service.unregisterAndReturnError_(None)
