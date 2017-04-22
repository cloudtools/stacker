from troposphere import Output, Ref
from stacker.blueprints.base import Blueprint
from troposphere.cloudformation import WaitConditionHandle


class Dummy(Blueprint):
    def create_template(self):
        handle = self.template.add_resource(
            WaitConditionHandle("DummyResource"))
        self.template.add_output(Output("DummyOutput", Value=Ref(handle)))
