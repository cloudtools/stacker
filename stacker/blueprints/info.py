from .variables.types import (
    CFNType,
    TroposphereType,
)
from ..util import load_object_from_string


def format_var_type(var_type):
    """Format a given var type to be displayed by the info command.

    Args:
        var_type (type): type of variable

    Returns:
        str: formatted display variable type

    """
    is_list = False
    if isinstance(var_type, TroposphereType):
        var_type = var_type.type

    if isinstance(var_type, list) and len(var_type):
        is_list = True
        var_type = var_type[0]

    if isinstance(var_type, CFNType):
        parts = ["{}::{}".format("CFN", var_type.parameter_type)]
    else:
        parts = [var_type.__name__]
        module = getattr(var_type, "__module__", None)
        if module == "__builtin__":
            module = None

        if module:
            parts.insert(0, module)

    formatted_type = ".".join(parts)
    return "[{}]".format(formatted_type) if is_list else formatted_type


def get_troposphere_type(var_type):
    """Return the wrapped type from a TroposphereType.

    Args:
        var_type (:class:`stacker.blueprints.variables.types.TroposphereType`):
            wrapped type

    Returns:
        type: wrapped inner troposphere type

    """
    troposphere_type = var_type.type
    if isinstance(var_type.type, list):
        troposphere_type = var_type.type[0]
    return troposphere_type


def explain_variable_field(variable, field_path):
    """Format information for a field of a given variable.

    Args:
        variable (dict): blueprint variable
        field_path (list): path to the field within the variable

    Returns:
        str: formatted string describing the field for the given variable.

    """
    var_type = variable["type"]
    # TODO does this handle cases where we don't have a troposphere type here?
    troposphere_type = get_troposphere_type(var_type)

    while field_path:
        prop_name = field_path.pop(0)
        prop_type, required = troposphere_type.props[prop_name]
        if isinstance(prop_type, list) and len(prop_type) == 1:
            prop_type = prop_type[0]

        if hasattr(prop_type, "props"):
            troposphere_type = prop_type

    fields = ""
    description = [format_var_type(prop_type)]
    if not hasattr(prop_type, "props"):
        if required:
            description.apppend("required")
    else:
        fields = get_fields_from_troposphere_type(prop_type)
        fields = "\n\nFields:\n%s" % "\n".join(fields)
    description = " ({})".format(", ".join(description))

    info = """
%(name)s%(description)s%(fields)s
    """ % {
        "name": prop_name,
        "description": description,
        "fields": fields,
    }
    print info


def get_fields_from_troposphere_type(troposphere_type):
    """Return all fields for a troposphere type formatted for display.

    Args:
        troposphere_type (type): troposphere type whose fields we're
            formatting.

    Returns:
        list: list of fields to display for the type

    """
    required_fields = []
    optional_fields = []
    for prop, prop_def in troposphere_type.props.items():
        prop_type, required = prop_def
        description = [format_var_type(prop_type)]
        if required:
            description.append("required")
        formatted = "- {} ({})".format(
            prop,
            ", ".join(description),
        )
        if required:
            required_fields.append(formatted)
        else:
            optional_fields.append(formatted)
    return required_fields + optional_fields


def get_variable_fields(variable):
    """Return the fields for the variable.

    This will return the fields that can be passed to any troposphere types.

    Args:
        variable (dict): blueprint variable definition

    Returns:
        str: formatted string that can be used to display fields a variable
            accepts.

    """
    var_type = variable["type"]
    if not isinstance(var_type, TroposphereType):
        return ""

    troposphere_type = get_troposphere_type(var_type)
    fields = get_fields_from_troposphere_type(troposphere_type)
    return "\n\nFields:\n%s" % "\n".join(fields)


def explain_variable(name, variable):
    """Output information related to the variable.

    Args:
        name (str): variable name
        variable (dict): variable definition

    """
    var_type = variable["type"]
    description = variable.get("description", "")
    if description:
        description = ": {}".format(description)

    info = """
%(name)s (%(type)s)%(description)s%(fields)s
    """ % {
        "name": name,
        "type": format_var_type(var_type),
        "description": description,
        "fields": get_variable_fields(variable),
    }
    print info


def explain_variable_path(path):
    """Output an explanation of the variable represented by the path.

    Args:
        path (list): an array of the path to the blueprint and the path to the
            variable we want to explain within the blueprint

    """
    class_path = path[0]
    variable_path = path[1]
    variable_path = variable_path.split(".")

    blueprint_class = load_object_from_string(class_path)
    variable = blueprint_class.VARIABLES[variable_path[0]]
    if len(variable_path) > 1:
        explain_variable_field(variable, variable_path[1:])
    else:
        explain_variable(variable_path[0], variable)


def explain_blueprint(path):
    """Output an explanation of the blueprint represented by the path.

    Args:
        path (list): an array of the path to the blueprint to explain

    """
    class_path = path[0]

    blueprint_class = load_object_from_string(class_path)
    formatted_variables = []
    for variable_name, variable_def in blueprint_class.VARIABLES.items():
        formatted = "- {} ({})".format(
            variable_name,
            format_var_type(variable_def["type"]),
        )
        description = variable_def.get("description")
        if description:
            formatted += ": {}".format(description)
        formatted_variables.append(formatted)

    info = """
%(name)s

Variables:
%(variables)s
    """ % {
        "name": blueprint_class.__name__,
        "variables": "\n".join(formatted_variables),
    }
    print info


def explain_path(path):
    """Explain the given path.

    Args:
        path (str): path to a stacker blueprint or variable path within a
            blueprint

    """
    paths = path.split(":", 1)
    if len(paths) > 1:
        return explain_variable_path(paths)
    return explain_blueprint(paths)
