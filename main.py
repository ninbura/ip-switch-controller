# Import StreamController modules
from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder

# Import actions
from .actions.SwitchInputAction.SwitchInputAction import SwitchInputAction

class TesmartController(PluginBase):
    def __init__(self):
        super().__init__()

        self.switch_input_holder = ActionHolder(
            plugin_base=self,
            action_base=SwitchInputAction,
            action_id="dev_ninbura_TesmartController::SwitchInput",
            action_name="Switch Input",
        )
        self.add_action_holder(self.switch_input_holder)

        self.register(
            plugin_name="TeSmart Controller",
            github_repo="https://github.com/ninbura/tesmart-controller",
            plugin_version="1.0.0",
            app_version="1.1.1-alpha"
        )