from .. import exceptions


class BaseProvider(object):

    name = None

    def __init__(self, *args, **kwargs):
        if not self.name:
            raise exceptions.ImproperlyConfigured('Provider must have a "name"')

    def _not_implemented_erorr(self, method):
        raise NotImplementedError('Provider "%s" does not support "%s"' % (self.name, method))

    def get_stack(self, stack_name, *args, **kwargs):
        self._not_implemented_erorr('get_stack')

    def create_stack(self, *args, **kwargs):
        self._not_implemented_erorr('create_stack')

    def update_stack(self, *args, **kwargs):
        self._not_implemented_erorr('update_stack')

    def destroy_stack(self, *args, **kwargs):
        self._not_implemented_erorr('destroy_stack')

    def get_stack_status(self, stack_name, *args, **kwargs):
        self._not_implemented_erorr('get_stack_status')
