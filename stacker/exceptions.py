class StackDoesNotExist(Exception):

    def __init__(self, stack_name, *args, **kwargs):
        message = 'Stack: "%s" does not exist in outputs' % (stack_name,)
        super(StackDoesNotExist, self).__init__(message, *args, **kwargs)


class MissingParameterException(Exception):

    def __init__(self, parameters, *args, **kwargs):
        self.parameters = parameters
        message = 'Missing required cloudformation parameters: %s' % (
            ', '.join(parameters),
        )
        super(MissingParameterException, self).__init__(message, *args,
                                                        **kwargs)


class MissingLocalParameterException(Exception):

    def __init__(self, parameter, *args, **kwargs):
        self.parameter = parameter
        message = 'Missing required local parameter: %s' % parameter
        super(MissingLocalParameterException, self).__init__(message, *args,
                                                             **kwargs)


class OutputDoesNotExist(Exception):

    def __init__(self, stack_name, output, *args, **kwargs):
        self.stack_name = stack_name
        self.output = output

        message = 'Output %s does not exist on stack %s' % (output,
                                                            stack_name)
        super(OutputDoesNotExist, self).__init__(message, *args, **kwargs)


class MissingEnvironment(Exception):

    def __init__(self, key, *args, **kwargs):
        self.key = key
        message = "Environment missing key %s." % (key,)
        super(MissingEnvironment, self).__init__(message, *args, **kwargs)


class ImproperlyConfigured(Exception):

    def __init__(self, cls, error, *args, **kwargs):
        message = 'Class "%s" is improperly configured: %s' % (
            cls,
            error,
        )
        super(ImproperlyConfigured, self).__init__(message, *args, **kwargs)


class StackDidNotChange(Exception):
    """Exception raised when there are no changes to be made by the
    provider.
    """
