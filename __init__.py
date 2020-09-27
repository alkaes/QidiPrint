from . import QidiPrintPlugin
from . import QidiMachineConfig
from UM.i18n import i18nCatalog
catalog = i18nCatalog("cura")


def getMetaData():
    return {}

def register(app):
    return {
        "output_device": QidiPrintPlugin.QidiPrintPlugin(),
        "machine_action": QidiMachineConfig.QidiMachineConfig()
    }
