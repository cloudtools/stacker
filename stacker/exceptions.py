

class StackDoesNotExist(Exception):

    def __init__(self, stack_name, *args, **kwargs):
        message = 'Stack: "%s" does not exist in outputs' % (stack_name,)
        super(StackDoesNotExist, self).__init__(message, *args, **kwargs)


class MissingParameterException(Exception):

    def __init__(self, parameters, *args, **kwargs):
        self.parameters = parameters
        message = 'Missing required parameters: %s' % (
            ', '.join(parameters),
        )
        super(MissingParameterException, self).__init__(message, *args, **kwargs)


class ParameterDoesNotExist(Exception):

    def __init__(self, parameter, *args, **kwargs):
        message = 'Parameter: "%s" does not exist in output' % (parameter,)
        super(ParameterDoesNotExist, self).__init__(message, *args, **kwargs)


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
