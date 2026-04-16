from . import LockboxModule
from ...attributes import FloatProperty, BoolProperty, StringProperty, BoolIgnoreProperty
from ...module_attributes import ModuleDictProperty
from ...pyrpl_utils import recursive_getattr
from ...modules import SignalLauncher
from ...hardware_modules import InputSelectProperty
from ...widgets.module_widgets import LockboxStageWidget, StageOutputWidget
from qtpy import QtCore
from pyrpl.async_utils import sleep_async, ensure_future, wait


class StageSignalLauncher(SignalLauncher):
    stage_created = QtCore.Signal(list)
    stage_deleted = QtCore.Signal(list)
    # stage_renamed = QtCore.Signal()


class StageOutput(LockboxModule):
    _setup_attributes = ["lock_on", "reset_offset", "offset"]
    _gui_attributes = _setup_attributes
    _widget_class = StageOutputWidget
    lock_on = BoolIgnoreProperty(default=False, call_setup=True)
    reset_offset = BoolProperty(default=False, call_setup=True)
    offset = FloatProperty(default=0, min=-1.0, max=1.0, increment=1e-4, call_setup=True)

    def _setup(self):
        # forward changes to parent module
        self.parent._setup()


class StageInputSelectProperty(InputSelectProperty):
    pass
    # def validate_and_normalize(self, obj, value):
    #    if isinstance(value, SignalModule):
    #        value = SignalModule.name
    #    return value


class Stage(LockboxModule):
    """
    A stage is a single step in the lock acquisition process
    """

    _gui_attributes = ["input", "setpoint", "duration", "gain_factor", "function_call"]
    _setup_attributes = _gui_attributes + ["outputs"]
    _widget_class = LockboxStageWidget
    _signal_launcher = StageSignalLauncher

    input = StageInputSelectProperty(
        ignore_errors=True,
        options=lambda stage: stage.lockbox.inputs.keys(),
        call_setup=True,
    )

    setpoint = FloatProperty(default=0, min=-1e6, max=1e6, increment=0.1, call_setup=True)

    gain_factor = FloatProperty(default=1.0, min=-1e6, max=1e6, increment=0.1, call_setup=True)

    function_call = StringProperty(default="", call_setup=True)

    duration = FloatProperty(default=0, min=0, max=1e6, increment=0.1)

    # outputs is a dict of submodules, containing an entry of
    # StageOutput per Lockbox output (initialized in __init__)
    outputs = ModuleDictProperty(module_cls=LockboxModule)

    def __init__(self, parent, name=None):
        super().__init__(parent, name=name)
        for output in self.lockbox.outputs:
            self.outputs[output.name] = StageOutput
        self._signal_launcher.stage_created.emit([self])
        self.parent._signal_launcher.stage_created.emit([self])
        self.lockbox._logger.debug(f"Stage {self.name} initialized")

    def _clear(self):
        self.lockbox._logger.debug(f"Deleting stage {self.name}")
        self._signal_launcher.stage_deleted.emit([self])
        self.parent._signal_launcher.stage_deleted.emit([self])
        super()._clear()

    @property
    def _states(self):
        """
        Returns the config file branch corresponding to the saved states of the module.
        """
        return None  # saving individual stage states is not allowed
        # return self.c._root._get_or_create("stage_" + str(self.name) + "_states")

    def execute_async(self):
        return ensure_future(self._execute_async())

    def execute(self):
        return wait(self.execute_async())

    def _enable(self):
        """
        Setup the lockbox parameters according to this stage
        """
        for output in self.lockbox.outputs:
            setting = self.outputs[output.name]
            if setting.lock_on == "ignore":
                # this part is here to remind you that BoolIgnoreProperties
                # should not be typecasted into bools, i.e. you should avoid
                # to write "if setting.lock_on: do_sth()" because the setting
                # 'ignore' will be interpreted identically as "True"
                pass
            if not setting.lock_on:
                output.unlock()
            if setting.reset_offset:
                output._setup_offset(setting.offset)
        # make a new iteration for enabling lock, in order
        # to be sure that all offsets are reset before starting lock
        for output in self.lockbox.outputs:
            setting = self.outputs[output.name]
            if setting.lock_on:
                output.lock(
                    input=self.input,
                    setpoint=self.setpoint,
                    offset=setting.offset if setting.reset_offset else None,
                    gain_factor=self.gain_factor,
                )
        # optionally call a user function at the end of the stage
        if self.function_call != "":
            try:
                func = recursive_getattr(self.lockbox, self.function_call)
            except AttributeError:
                self._logger.warning(
                    "Could not find the function '%s' called "
                    "in stage %s in the Lockbox class. "
                    "Please specify a valid function name "
                    "to call!",
                    self.function_call,
                    self.name,
                )
            else:
                try:
                    func()
                except TypeError:
                    func(self)
        # set lockbox state to stage name
        self.lockbox.current_state = self.name

    async def _execute_async(self):
        if self.lockbox._monitor_lock_status_task is None:
            self.lockbox._monitor_lock_status_task = ensure_future(
                self.lockbox._monitor_lock_status_async()
            )
        self._enable()
        await sleep_async(self.duration)
        if self.lockbox.sequence[-1] == self:
            self.lockbox.current_state = "lock_on"

    def _setup(self):
        # the first test is needed to avoid startup problems
        if hasattr(self.lockbox, "_sequence"):
            if self.lockbox.current_state == self.name:
                # enable a stage if its parameters have changed
                self.execute_async()
            # synchronize (active) final_stage with the last stage of sequence
            elif self.lockbox.current_state == "lock" and self == self.parent[-1]:
                self.lockbox.final_stage = self.setup_attributes
