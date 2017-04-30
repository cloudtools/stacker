==========
Blueprints
==========

Blueprints are python classes that build CloudFormation templates.
Traditionally these are built using troposphere_, but that is not absolutely
necessary. You are encouraged to check out the library of publicly shared
Blueprints in the stacker_blueprints_ package.

Making your own should be easy, and you can take a lot of examples from
stacker_blueprints_. In the end, all that is required is that the Blueprint
is a subclass of *stacker.blueprints.base* and it have the following methods::

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

The ``TroposphereType`` can be used to create one or more Troposphere
types by directly passing in the value from the config to the specified
Troposphere type.

Example
^^^^^^^

Below is an annotated example::

  from stacker.blueprints.base import Blueprint
  from stacker.blueprints.variables.types import TroposphereType
  from troposphere import s3


  class Buckets(Blueprint):

      VARIABLES = {
          "Buckets": {
              # Specify that Buckets will be a list of s3.Bucket types.
              This means the config should take a list of dictionaries
              which will be converted into troposphere buckets.
              "type": TroposphereType(s3.Bucket, many=True),
              "description": "S3 Buckets to create.",
          },
          "SingleBucket": {
              # Specify that only a single bucket can be passed.
              "type": TroposphereType(s3.Bucket),
              "description": "A single S3 bucket",
          },
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

A sample config for the above::

  stacks:
    - name: buckets
      class_path: path.to.above.Buckets
      variables:
        Buckets:
          # resource name that will be added to CloudFormation
          FirstBucket:
            # name of the s3 bucket
            BucketName: my-first-bucket
          SecondBucket:
            BucketName: my-second-bucket
        SingleBucket:
          BucketName: my-single-bucket

CFNType
-------

The ``CFNType`` can be used to signal that a variable should be submitted
to CloudFormation as a Parameter instead of only available to the
Blueprint when rendering. This is useful if you want to leverage AWS
specific Parameter types like ``List<AWS::EC2::Image::Id>``. See
``stacker.blueprints.variables.types`` for available subclasses of the
``CFNType``.

Example
^^^^^^^

Below is an annotated example::


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
            value>. For the sublcasses of `CFNType`, the values are
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

.. _troposphere: https://github.com/cloudtools/troposphere
.. _stacker_blueprints: https://github.com/remind101/stacker_blueprints
.. _Route53 DNSRecords Blueprint: https://github.com/remind101/stacker_blueprints/blob/master/tests/test_route53.py
.. _output results: https://github.com/remind101/stacker_blueprints/tree/master/tests/fixtures/blueprints
