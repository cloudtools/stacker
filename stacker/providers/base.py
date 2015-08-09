def not_implemented(method):
    raise NotImplementedError("Provider does not support '%s' "
                              "method." % method)


class BaseProvider(object):
    def get_stack(self, stack_name, *args, **kwargs):
        not_implemented("get_stack")

    def create_stack(self, *args, **kwargs):
        not_implemented("create_stack")

    def update_stack(self, *args, **kwargs):
        not_implemented("update_stack")

    def destroy_stack(self, *args, **kwargs):
        not_implemented("destroy_stack")

    def get_stack_status(self, stack_name, *args, **kwargs):
        not_implemented("get_stack_status")

    def get_outputs(self, stack_name, *args, **kwargs):
        not_implemented("get_outputs")

    def get_output(self, stack_name, output):
        return self.get_outputs(stack_name)[output]
