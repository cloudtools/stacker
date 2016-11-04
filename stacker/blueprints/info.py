from .variables.types import (
    CFNType,
    TroposphereType,
)
from ..util import load_object_from_string


def format_var_type(var_type):
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
    troposphere_type = var_type.type
    if isinstance(var_type.type, list):
        troposphere_type = var_type.type[0]
    return troposphere_type


def explain_variable_field(variable, field_path):
    var_type = variable["type"]
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
    var_type = variable["type"]
    if not isinstance(var_type, TroposphereType):
        return ""

    troposphere_type = get_troposphere_type(var_type)
    fields = get_fields_from_troposphere_type(troposphere_type)
    return "\n\nFields:\n%s" % "\n".join(fields)


def explain_variable(name, variable):
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


def get_variable_info(paths):
    class_path = paths[0]
    variable_path = paths[1]
    variable_paths = variable_path.split('.')

    blueprint_class = load_object_from_string(class_path)
    variable = blueprint_class.VARIABLES[variable_paths[0]]
    if len(variable_paths) > 1:
        explain_variable_field(variable, variable_paths[1:])
    else:
        explain_variable(variable_paths[0], variable)


def get_blueprint_info(paths):
    class_path = paths[0]

    blueprint_class = load_object_from_string(class_path)
    formatted_variables = []
    for variable_name, variable_def in blueprint_class.VARIABLES.items():
        formatted = "\t- {} ({})".format(
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
        "variables": '\n'.join(formatted_variables),
    }
    print info


def explain_blueprint(path):
    paths = path.split(":", 1)
    if len(paths) > 1:
        return get_variable_info(paths)
    return get_blueprint_info(paths)
