import cellprofiler.module
import cellprofiler.setting
import imagej

BOOL_TYPES = [
    "boolean",
    "java.lang.Boolean"
]

COLOR_TYPES = ["org.scijava.util.ColorRGB"]

FILE_TYPES = ["java.io.File"]

FLOAT_TYPES = [
    "double",
    "float",
    "java.lang.Double",
    "java.lang.Float",
    "java.math.BigDecimal"
]

IGNORE_TYPES = [
    "org.scijava.widget.Button"  # For now!
]

IMAGE_TYPES = [
    "net.imagej.Dataset",
    "net.imagej.display.DataView",
    "net.imagej.display.DatasetView",
    "net.imagej.display.ImageDisplay",
    "net.imglib2.IterableInterval",
    "net.imglib2.RandomAccessibleInterval",
    "net.imglib2.img.*Img"
]

INTEGER_TYPES = [
    "byte",
    "int",
    "long",
    "short",
    "java.lang.Byte",
    "java.lang.Integer",
    "java.lang.Long",
    "java.lang.Short",
    "java.math.BigInteger"
]

TEXT_TYPES = [
    "char",
    "java.lang.Character",
    "java.lang.String",
    "java.util.Date"
]

# To start CellProfiler with the plugins directory:
#   `pythonw -m cellprofiler --plugins-directory .`
class RunImageJ(cellprofiler.module.ImageProcessing):
    module_name = "RunImageJ"
    variable_revision_number = 1

    @staticmethod
    def get_ij_modules():
        # TODO: configure the ImageJ server host in CellProfiler's preferences.
        # Not sure we can do this via CellProfiler-plugins but maaaaaybeeee?
        # Otherwise, we'll need to expose this via a setting or an env variable.
        #
        # I tried exposing this through a setting and calling on_setting_changed
        # when the host was updated; on_setting_change would repopulate the
        # module choices using this method. However, there isn't a choices setter
        # on the Choice setting. :(
        ij = imagej.IJ()
        modules = ij.modules()
        modules = [module.split(".")[-1] for module in modules if RunImageJ.is_friendly_module(module)]
        return sorted(modules)

    @staticmethod
    def is_friendly_module(module):
        # TODO: Filter modules by headless flag. Server needs to give more info.
        # That said: server should just have a mode for headless-only or not.
        # Then we won't have to detail every module up front anyway.
        return True

    def on_setting_changed(self, setting, pipeline):
        if not setting == self.ijmodule:
            return

        self.create_ijsettings(setting.value)

    def create_ijsettings(self, module_name):
        self.ijsettings = cellprofiler.setting.SettingsGroup()

        # Get the module and the module details
        ij = imagej.IJ()
        module = ij.find(module_name)[0]
        details = ij.detail(module)
        inputs = details["inputs"]

        # # FOR DEBUGGING
        # import json
        # print(json.dumps(details, indent=4))

        for input_ in inputs:
            name = input_["name"]
            default_value = input_["defaultValue"]
            input_["rawType"] = raw_type = input_["genericType"].split("<")[0].split(" ")[-1]

            # HACK: For now, we skip service and context parameters.
            # Later, the ImageJ Server will filter these out for us.
            if raw_type.endswith("Service") or raw_type == "org.scijava.Context":
                continue

            # TODO:
            # - Exclude inappropriate visibilities
            #   But ImageJ server does not tell us right now
            # - Add outputs

            setting = self.make_setting(input_)
            if setting is not None:
                self.ijsettings.append(name, setting)

    def make_setting(self, input_):
        raw_type = input_["rawType"]
        if raw_type in IGNORE_TYPES:
            # print("**** Ignoring input: '" + input_["name"] + "' of type '" + raw_type + "' ****")
            return None

        label = input_["label"]
        text = label if not (label is None or label == "") else input_["name"]
        value = input_["defaultValue"]
        minval = input_["minimumValue"]
        maxval = input_["maximumValue"]
        style = input_["widgetStyle"].lower()

        if raw_type in BOOL_TYPES:
            return cellprofiler.setting.Binary(text, value)

        if raw_type in COLOR_TYPES:
            return cellprofiler.setting.Color(text, value)

        if raw_type in FILE_TYPES:
            if style.startswith("directory"):
                # TODO: Massage non-None value to CellProfiler-friendly string.
                return cellprofiler.setting.DirectoryPath(text)

            # "open" or "save" or unspecified
            # TODO: Use a fancier combination of widgets.
            return cellprofiler.setting.Pathname(text, value if value else '')

        if raw_type in FLOAT_TYPES:
            return cellprofiler.setting.Float(text, self.clamp(value, minval), minval, maxval)

        if raw_type in IMAGE_TYPES:
            return cellprofiler.setting.ImageNameSubscriber(text)

        if raw_type in INTEGER_TYPES:
            return cellprofiler.setting.Integer(text, self.clamp(value, minval), minval, maxval)

        if raw_type in TEXT_TYPES:
            choices = input_["choices"]
            if choices is None:
                if style.startswith("text area"):
                    return cellprofiler.setting.Text(text, value, multiline=True)
                return cellprofiler.setting.Text(text, value)

            return cellprofiler.setting.Choice(text, choices)

        # TODO: handle error somehow -- maybe put a label saying "unsupported input: blah"
        # print("**** Unsupported input: '" + input_["name"] + "' of type '" + raw_type + "' ****")
        return None

    def clamp(self, value, minval):
        if value:
            return value

        return minval if minval else 0

    # Define settings as instance variables
    # Available settings are in in cellprofiler.settings
    #
    # The superclass creates the following settings:
    #   - self.x_name: cellprofiler.setting.ImageNameSubscriber, the input image
    #   - self.y_name: cellprofiler.setting.ImageNameProvider, the output image
    def create_settings(self):
        super(RunImageJ, self).create_settings()

        self.ijmodule = cellprofiler.setting.Choice(
            "ImageJ module",
            choices=self.get_ij_modules()
        )

        self.create_ijsettings(self.ijmodule.value)

    # Returns the list of available settings
    # This is primarily used to load/save the .cppipe/.cpproj files
    #
    # The superclass returns:
    #   - [self.x_name, self.y_name]
    def settings(self):
        settings = super(RunImageJ, self).settings()

        settings.append(self.ijmodule)
        settings += self.ijsettings.settings

        return settings

    # Returns a list of settings which are available to the GUI.
    # By default, this is `settings`. Conditional logic can be used
    # to activate and deactivate GUI options.
    def visible_settings(self):
        visible_settings = super(RunImageJ, self).visible_settings()

        visible_settings.append(self.ijmodule)
        visible_settings += self.ijsettings.settings

        return visible_settings

    def run(self, workspace):
        self.function = lambda x: x

        super(RunImageJ, self).run(workspace)
