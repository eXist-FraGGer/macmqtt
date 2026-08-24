from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt


def accessibility_trusted():
    return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: False}))


def request_accessibility():
    """Shows the macOS permission prompt and returns True if already granted."""
    return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}))
