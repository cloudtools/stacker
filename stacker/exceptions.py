class InvalidLookupCombination(Exception):

    def __init__(self, lookup, lookups, value, *args, **kwargs):
        message = (
            "Lookup: \"{}\" has non-string return value, must be only lookup "
            "present (not {}) in \"{}\""
        ).format(lookup.raw, len(lookups), value)
        super(InvalidLookupCombination, self).__init__(message,
                                                       *args,
                                                       **kwargs)


class UnknownLookupType(Exception):

    def __init__(self, lookup, *args, **kwargs):
        message = "Unknown lookup type: \"{}\"".format(lookup.type)
        super(UnknownLookupType, self).__init__(message, *args, **kwargs)


class UnresolvedVariables(Exception):

    def __init__(self, blueprint_name, *args, **kwargs):
        message = "Blueprint: \"%s\" hasn't resolved it's variables" % (
            blueprint_name)
        super(UnresolvedVariables, self).__init__(message, *args, **kwargs)


class UnresolvedVariable(Exception):

    def __init__(self, blueprint_name, variable, *args, **kwargs):
        message = (
            "Variable \"%s\" in blueprint \"%s\" hasn't been resolved" % (
                variable.name, blueprint_name
            )
        )
        super(UnresolvedVariable, self).__init__(message, *args, **kwargs)


class MissingVariable(Exception):

    def __init__(self, blueprint_name, variable_name, *args, **kwargs):
        message = "Variable \"%s\" in blueprint \"%s\" is missing" % (
            variable_name, blueprint_name)
        super(MissingVariable, self).__init__(message, *args, **kwargs)


class VariableTypeRequired(Exception):

    def __init__(self, blueprint_name, variable_name, *args, **kwargs):
        message = (
            "Variable \"%s\" in blueprint \"%s\" does not have a type" % (
                variable_name, blueprint_name)
        )
        super(VariableTypeRequired, self).__init__(message, *args, **kwargs)


class StackDoesNotExist(Exception):

    def __init__(self, stack_name, *args, **kwargs):
        message = "Stack: \"%s\" does not exist in outputs" % (stack_name,)
        super(StackDoesNotExist, self).__init__(message, *args, **kwargs)


class MissingParameterException(Exception):

    def __init__(self, parameters, *args, **kwargs):
        self.parameters = parameters
        message = "Missing required cloudformation parameters: %s" % (
            ", ".join(parameters),
        )
        super(MissingParameterException, self).__init__(message, *args,
                                                        **kwargs)


class OutputDoesNotExist(Exception):

    def __init__(self, stack_name, output, *args, **kwargs):
        self.stack_name = stack_name
        self.output = output

        message = "Output %s does not exist on stack %s" % (output,
                                                            stack_name)
        super(OutputDoesNotExist, self).__init__(message, *args, **kwargs)


class MissingEnvironment(Exception):

    def __init__(self, key, *args, **kwargs):
        self.key = key
        message = "Environment missing key %s." % (key,)
        super(MissingEnvironment, self).__init__(message, *args, **kwargs)


class ImproperlyConfigured(Exception):

    def __init__(self, cls, error, *args, **kwargs):
        message = "Class \"%s\" is improperly configured: %s" % (
            cls,
            error,
        )
        super(ImproperlyConfigured, self).__init__(message, *args, **kwargs)


class StackDidNotChange(Exception):
    """Exception raised when there are no changes to be made by the
    provider.
    """


class CancelExecution(Exception):
    """Exception raised when we want to cancel executing the plan."""


class ValidatorError(Exception):
    """Used for errors raised by custom validators of blueprint variables.
    """
    def __init__(self, variable, validator, value, exception=None):
        self.variable = variable
        self.validator = validator
        self.value = value
        self.exception = exception
        self.message = ("Validator '%s' failed for variable '%s' with value "
                        "'%s'") % (self.validator, self.variable, self.value)

        if self.exception:
            self.message += ": %s: %s" % (self.exception.__class__.__name__,
                                          str(self.exception))

    def __str__(self):
        return self.message
