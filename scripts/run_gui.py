# py2app entry point. Kept outside the macmqtt package: py2app's "app"
# script must not itself be a package member (no relative imports).
from macmqtt.gui.app import main

if __name__ == "__main__":
    main()
