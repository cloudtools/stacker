==========
Blueprints
==========

Blueprints are python classes that build CloudFormation templates.
Traditionally these are built using troposphere_, but that is not absolutely
necessary. You are encouraged to check out the library of publicly shared
Blueprints in the stacker_blueprints_ package.

Making your own should be easy, and you can take a lot of examples from
stacker_blueprints_. In the end, all that is required is that the Blueprint
is a subclass of *stacker.blueprints.base* and it have the following methods:

.. code-block:: python

    # Initializes the blueprint
    def __init__(self, name, context, mappings=None):

    # Updates self.template to create the actual template
    def create_template(self):

    # Returns a tuple: (version, rendered_template)
    def render_template(self):

Variables
=========

A Blueprint can define a ``VARIABLES`` property that defines the variables
it accepts from the `Config Variables <config.html#variables>`_.

``VARIABLES`` should be a dictionary of ``<variable name>: <variable
definition>``. The variable definition should be a dictionary which
supports the following optional keys:

**type:**
  The type for the variable value. This can either be a native python
  type or one of the `Variable Types`_.

**default:**
  The default value that should be used for the variable if none is
  provided in the config.

**description:**
  A string that describes the purpose of the variable.

**validator:**
  An optional function that can do custom validation of the variable. A
  validator function should take a single argument, the value being validated,
  and should return the value if validation is successful. If there is an
  issue validating the value, an exception (``ValueError``, ``TypeError``, etc)
  should be raised by the function.

**no_echo:**
  Only valid for variables whose type subclasses ``CFNType``. Whether to
  mask the parameter value whenever anyone makes a call that describes the
  stack. If you set the value to true, the parameter value is masked with
  asterisks (*****).

**allowed_values:**
  Only valid for variables whose type subclasses ``CFNType``. The set of
  values that should be allowed for the CloudFormation Parameter.

**allowed_pattern:**
  Only valid for variables whose type subclasses ``CFNType``. A regular
  expression that represents the patterns you want to allow for the
  CloudFormation Parameter.

**max_length:**
  Only valid for variables whose type subclasses ``CFNType``. The maximum
  length of the value for the CloudFormation Parameter.

**min_length:**
  Only valid for variables whose type subclasses ``CFNType``. The minimum
  length of the value for the CloudFormation Parameter.

**max_value:**
  Only valid for variables whose type subclasses ``CFNType``. The max
  value for the CloudFormation Parameter.

**min_value:**
  Only valid for variables whose type subclasses ``CFNType``. The min
  value for the CloudFormation Parameter.

**constraint_description:**
  Only valid for variables whose type subclasses ``CFNType``. A string
  that explains the constraint when the constraint is violated for the
  CloudFormation Parameter.


Variable Types
==============

Any native python type can be specified as the ``type`` for a variable.
You can also use the following custom types:

TroposphereType
---------------

The ``TroposphereType`` can be used to generate resources for use in the
blueprint directly from user-specified configuration. Which case applies depends
on what ``type`` was chosen, and how it would be normally used in the blueprint
(and CloudFormation in general).

Resource Types
^^^^^^^^^^^^^^

When ``type`` is a `Resource Type`_, the value specified by the user in the
configuration file must be a dictionary, but with two possible structures.

When ``many`` is disabled, the top-level dictionary keys correspond to
parameters of the ``type`` constructor. The key-value pairs will be used
directly, and one object will be created and stored in the variable.

When ``many`` is enabled, the top-level dictionary *keys* are resource titles,
and the corresponding *values* are themselves dictionaries, to be used as
parameters for creating each of multiple ``type`` objects. A list of those
objects will be stored in the variable.

Property Types
^^^^^^^^^^^^^^

When ``type`` is a `Property Type`_ the value specified by the user in the
configuration file must be a dictionary or a list of dictionaries.

When ``many`` is disabled, the top-level dictionary keys correspond to
parameters of the ``type`` constructor. The key-value pairs will be used
directly, and one object will be created and stored in the variable.

When ``many`` is enabled, a list of dictionaries is expected. For each element,
one corresponding call will be made to the ``type`` constructor, and all the
objects produced will be stored (also as a list) in the variable.

Optional variables
^^^^^^^^^^^^^^^^^^

In either case, when ``optional`` is enabled, the variable may have no value
assigned, or be explicitly assigned a null value. When that happens the
variable's final value will be ``None``.

Example
^^^^^^^

Below is an annotated example:

.. code-block:: python

    from stacker.blueprints.base import Blueprint
    from stacker.blueprints.variables.types import TroposphereType
    from troposphere import s3, sns

    class Buckets(Blueprint):

        VARIABLES = {
            # Specify that Buckets will be a list of s3.Bucket types.
            # This means the config should a dictionary of dictionaries
            # which will be converted into troposphere buckets.
            "Buckets": {
                "type": TroposphereType(s3.Bucket, many=True),
                "description": "S3 Buckets to create.",
            },
            # Specify that only a single bucket can be passed.
            "SingleBucket": {
                "type": TroposphereType(s3.Bucket),
                "description": "A single S3 bucket",
            },
            # Specify that Subscriptions will be a list of sns.Subscription types.
            # Note: sns.Subscription is the property type, not the standalone
            # sns.SubscriptionResource.
            "Subscriptions": {
                "type": TroposphereType(sns.Subscription, many=True),
                "description": "Multiple SNS subscription designations"
            },
            # Specify that only a single subscription can be passed, and that it
            # is made optional.
            "SingleOptionalSubscription": {
                "type": TroposphereType(sns.Subscription, optional=True),
                "description": "A single, optional SNS subscription designation"
            }
        }

        def create_template(self):
            t = self.template
            variables = self.get_variables()

            # The Troposphere s3 buckets have already been created when we
            access variables["Buckets"], we just need to add them as
            resources to the template.
            [t.add_resource(bucket) for bucket in variables["Buckets"]]

            # Add the single bucket to the template. You can use
            `Ref(single_bucket)` to pass CloudFormation references to the
            bucket just as you would with any other Troposphere type.
            single_bucket = variables["SingleBucket"]
            t.add_resource(single_bucket)

            subscriptions = variables["Subscriptions"]
            optional_subscription = variables["SingleOptionalSubscription"]
            # Handle it in some special way...
            if optional_subscription is not None:
                subscriptions.append(optional_subscription)

            t.add_resource(sns.Topic(
                TopicName="one-test",
                Subscriptions=))

            t.add_resource(sns.Topic(
                TopicName="another-test",
                Subscriptions=subscriptions))



A sample config for the above:

..  code-block:: yaml

    stacks:
      - name: buckets
        class_path: path.to.above.Buckets
        variables:
          Buckets:
            # resource name (title) that will be added to CloudFormation.
            FirstBucket:
              # name of the s3 bucket
              BucketName: my-first-bucket
            SecondBucket:
              BucketName: my-second-bucket
          SingleBucket:
            # resource name (title) that will be added to CloudFormation.
            MySingleBucket:
              BucketName: my-single-bucket
          Subscriptions:
            - Endpoint: one-lambda
              Protocol: lambda
            - Endpoint: another-lambda
              Protocol: lambda
          # The following could be ommited entirely
          SingleOptionalSubscription:
            Endpoint: a-third-lambda
            Protocol: lambda


CFNType
-------

The ``CFNType`` can be used to signal that a variable should be submitted
to CloudFormation as a Parameter instead of only available to the
Blueprint when rendering. This is useful if you want to leverage AWS-
Specific Parameter types (e.g. ``List<AWS::EC2::Image::Id>``) or Systems
Manager Parameter Store values (e.g. ``AWS::SSM::Parameter::Value<String>``).
See ``stacker.blueprints.variables.types`` for available subclasses of the
``CFNType``.

Example
^^^^^^^

Below is an annotated example:

.. code-block:: python

    from stacker.blueprints.base import Blueprint
    from stacker.blueprints.variables.types import (
        CFNString,
        EC2AvailabilityZoneNameList,
    )


    class SampleBlueprint(Blueprint):

        VARIABLES = {
            "String": {
                "type": str,
                "description": "Simple string variable",
            },
            "List": {
                "type": list,
                "description": "Simple list variable",
            },
            "CloudFormationString": {
                "type": CFNString,
                "description": "A variable which will create a CloudFormation Parameter of type String",
            },
            "CloudFormationSpecificType": {
                "type": EC2AvailabilityZoneNameList,
                "description": "A variable which will create a CloudFormation Parameter of type List<AWS::EC2::AvailabilityZone::Name>"
            },
        }

        def create_template(self):
            t = self.template

            # `get_variables` returns a dictionary of <variable name>: <variable
            value>. For the subclasses of `CFNType`, the values are
            instances of `CFNParameter` which have a `ref` helper property
            which will return a troposphere `Ref` to the parameter name.
            variables = self.get_variables()

            t.add_output(Output("StringOutput", variables["String"]))

            # variables["List"] is a native list
            for index, value in enumerate(variables["List"]):
                t.add_output(Output("ListOutput:{}".format(index), value))


            # `CFNParameter` values (which wrap variables with a `type`
            that is a `CFNType` subclass) can be converted to troposphere
            `Ref` objects with the `ref` property
            t.add_output(Output("CloudFormationStringOutput",
                                variables["CloudFormationString"].ref))
            t.add_output(Output("CloudFormationSpecificTypeOutput",
                                variables["CloudFormationSpecificType"].ref))


Utilizing Stack name within your Blueprint
==========================================

Sometimes your blueprint might want to utilize the already existing stack name
within your blueprint. Stacker provides access to both the fully qualified
stack name matching what’s shown in the CloudFormation console, in addition to
the stacks short name you have set in your YAML config.

Referencing Fully Qualified Stack name
--------------------------------------

The fully qualified name is a combination of the Stacker namespace + the short
name (what you set as `name` in your YAML config file). If your stacker
namespace is `StackerIsCool` and the stacks short name is
`myAwesomeEC2Instance`, the fully qualified name would be:

``StackerIsCool-myAwesomeEC2Instance``

To use this in your blueprint, you can get the name from context. The
``self.context.get_fqn(self.name)``

Referencing the Stack short name
--------------------------------

The Stack short name is the name you specified for the stack within your YAML
config. It does not include the namespace. If your stacker namespace is
`StackerIsCool` and the stacks short name is `myAwesomeEC2Instance`, the
short name would be:

``myAwesomeEC2Instance``

To use this in your blueprint, you can get the name from self.name: ``self.name``

Example
^^^^^^^

Below is an annotated example creating a security group:

.. code-block:: python

  # we are importing Ref to allow for CFN References in the EC2 resource.  Tags
  # will be used to set the Name tag
  from troposphere import Ref, ec2, Tags
  from stacker.blueprints.base import Blueprint
  # CFNString is imported to allow for stand alone stack use
  from stacker.blueprints.variables.types import CFNString

  class SampleBlueprint(Blueprint):

    # VpcId set here to allow for blueprint to be reused
    VARIABLES = {
    "VpcId": {
        "type": CFNString,
        "description": "The VPC to create the Security group in",
        }
    }


    def create_template(self):
        template = self.template
        # Assigning the variables to a variable
        variables = self.get_variables()
        # now adding a SecurityGroup resource named `SecurityGroup` to the CFN template
        template.add_resource(
          ec2.SecurityGroup(
            "SecurityGroup",
            # Refering the VpcId set as the varible
            VpcId=variables['VpcId'].ref,
            # Setting the group description as the fully qualified name
            GroupDescription=self.context.get_fqn(self.name),
            # setting the Name tag to be the stack short name
            Tags=Tags(
              Name=self.name
              )
            )
          )


Testing Blueprints
==================

When writing your own blueprints its useful to write tests for them in order
to make sure they behave the way you expect they would, especially if there is
any complex logic inside.

To this end, a sub-class of the `unittest.TestCase` class has been
provided: `stacker.blueprints.testutil.BlueprintTestCase`. You use it
like the regular TestCase class, but it comes with an addition assertion:
`assertRenderedBlueprint`. This assertion takes a Blueprint object and renders
it, then compares it to an expected output, usually in
`tests/fixtures/blueprints`.

Examples of using the `BlueprintTestCase` class can be found in the
stacker_blueprints repo. For example, see the tests used to test the
`Route53 DNSRecords Blueprint`_ and the accompanying `output results`_:

Yaml (stacker) format tests
---------------------------

In order to wrap the `BlueprintTestCase` tests in a format similar to stacker's
stack format, the `YamlDirTestGenerator` class is provided. When subclassed in
a directory, it will search for yaml files in that directory with certain
structure and execute a test case for it. As an example:

.. code-block:: yaml

  ---
  namespace: test
  stacks:
    - name: test_stack
      class_path: stacker_blueprints.s3.Buckets
      variables:
        var1: val1

When run from nosetests, this will create a template fixture file called
test_stack.json containing the output from the `stacker_blueprints.s3.Buckets`
template.

Examples of using the `YamlDirTestGenerator` class can be found in the
stacker_blueprints repo. For example, see the tests used to test the
`s3.Buckets`_ class and the accompanying `fixture`_. These are
generated from a `subclass of YamlDirTestGenerator`_.

.. _troposphere: https://github.com/cloudtools/troposphere
.. _stacker_blueprints: https://github.com/cloudtools/stacker_blueprints
.. _Route53 DNSRecords Blueprint: https://github.com/cloudtools/stacker_blueprints/blob/master/tests/test_route53.py
.. _output results: https://github.com/cloudtools/stacker_blueprints/tree/master/tests/fixtures/blueprints
.. _Resource Type: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-template-resource-type-ref.html
.. _Property Type: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-product-property-reference.html
.. _s3.Buckets: https://github.com/cloudtools/stacker_blueprints/blob/master/tests/test_s3.yaml
.. _fixture: https://github.com/cloudtools/stacker_blueprints/blob/master/tests/fixtures/blueprints/s3_static_website.json
.. _subclass of YamlDirTestGenerator: https://github.com/cloudtools/stacker_blueprints/blob/master/tests/__init__.py
