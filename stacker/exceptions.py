from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


class InvalidConfig(Exception):
    def __init__(self, errors):
        super(InvalidConfig, self).__init__(errors)
        self.errors = errors


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
        self.lookup = lookup
        message = "Unknown lookup type: \"{}\"".format(lookup.type)
        super(UnknownLookupType, self).__init__(message, *args, **kwargs)


class FailedVariableLookup(Exception):

    def __init__(self, variable_name, lookup, error, *args, **kwargs):
        self.lookup = lookup
        self.error = error
        message = "Couldn't resolve lookup in variable `%s`, " % variable_name
        message += "lookup: ${%s}: " % lookup.raw
        message += "(%s) %s" % (error.__class__, error)
        super(FailedVariableLookup, self).__init__(message, *args, **kwargs)


class InvalidUserdataPlaceholder(Exception):

    def __init__(self, blueprint_name, exception_message, *args, **kwargs):
        message = exception_message + ". "
        message += "Could not parse userdata in blueprint \"%s\". " % (
            blueprint_name)
        message += "Make sure to escape all $ symbols with a $$."
        super(InvalidUserdataPlaceholder, self).__init__(
            message, *args, **kwargs)


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
        message = ("Stack: \"%s\" does not exist in outputs or the lookup is "
                   "not available in this stacker run") % (stack_name,)
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


class ChangesetDidNotStabilize(Exception):
    def __init__(self, change_set_id):
        self.id = change_set_id
        message = "Changeset '%s' did not reach a completed state." % (
            change_set_id
        )

        super(ChangesetDidNotStabilize, self).__init__(message)


class UnhandledChangeSetStatus(Exception):
    def __init__(self, stack_name, change_set_id, status, status_reason):
        self.stack_name = stack_name
        self.id = change_set_id
        self.status = status
        self.status_reason = status_reason
        message = (
            "Changeset '%s' on stack '%s' returned an unhandled status "
            "'%s: %s'." % (change_set_id, stack_name, status,
                           status_reason)
        )

        super(UnhandledChangeSetStatus, self).__init__(message)


class UnableToExecuteChangeSet(Exception):
    def __init__(self, stack_name, change_set_id, execution_status):
        self.stack_name = stack_name
        self.id = change_set_id
        self.execution_status = execution_status

        message = ("Changeset '%s' on stack '%s' had bad execution status: "
                   "%s" % (change_set_id, stack_name, execution_status))

        super(UnableToExecuteChangeSet, self).__init__(message)


class StackUpdateBadStatus(Exception):

    def __init__(self, stack_name, stack_status, reason, *args, **kwargs):
        self.stack_name = stack_name
        self.stack_status = stack_status

        message = ("Stack: \"%s\" cannot be updated nor re-created from state "
                   "%s: %s" % (stack_name, stack_status, reason))
        super(StackUpdateBadStatus, self).__init__(message, *args, **kwargs)


class PlanFailed(Exception):

    def __init__(self, failed_steps, *args, **kwargs):
        self.failed_steps = failed_steps

        step_names = ', '.join(step.name for step in failed_steps)
        message = "The following steps failed: %s" % (step_names,)

        super(PlanFailed, self).__init__(message, *args, **kwargs)


class GraphError(Exception):
    """Raised when the graph is invalid (e.g. acyclic dependencies)
    """

    def __init__(self, exception, stack, dependency):
        self.stack = stack
        self.dependency = dependency
        self.exception = exception
        message = (
            "Error detected when adding '%s' "
            "as a dependency of '%s': %s"
        ) % (dependency, stack, str(exception))
        super(GraphError, self).__init__(message)
