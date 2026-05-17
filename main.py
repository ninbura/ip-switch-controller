from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder
from src.backend.PluginManager.ActionInputSupport import ActionInputSupport
from src.backend.DeckManagement.InputIdentifier import Input

from .features.tesmart.switch_input import TESmartSwitchInput
from .features.hdfury.switch_input import HDFurySwitchInput
from .features.tesmart.manager import TESmartManager
from .features.hdfury.manager import HDFuryManager

_ACTION_SUPPORT = {
    Input.Key: ActionInputSupport.SUPPORTED,
    Input.Dial: ActionInputSupport.UNSUPPORTED,
    Input.Touchscreen: ActionInputSupport.UNSUPPORTED,
}


class IpSwitchController(PluginBase):
    def __init__(self):
        super().__init__()

        self.tesmart = TESmartManager()
        self.hdfury = HDFuryManager()

        self.add_action_holder(ActionHolder(
            plugin_base=self,
            action_base=TESmartSwitchInput,
            action_id="dev_ninbura_IpSwitchController::TESmartSwitchInput",
            action_name="TESmart: Switch Input",
            action_support=_ACTION_SUPPORT,
        ))
        self.add_action_holder(ActionHolder(
            plugin_base=self,
            action_base=HDFurySwitchInput,
            action_id="dev_ninbura_IpSwitchController::HDFurySwitchInput",
            action_name="HDFury: Switch Input",
            action_support=_ACTION_SUPPORT,
        ))

        self.register(
            plugin_name="IP Switch Controller",
            github_repo="https://github.com/ninbura/tesmart-controller",
            plugin_version="1.0.0",
            app_version="1.1.1-alpha"
        )
