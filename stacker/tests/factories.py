

def generate_definition(base_name, stack_id, **overrides):
    definition = {
        "name": "%s.%d" % (base_name, stack_id),
        "class_path": "stacker.blueprints.%s.%s" % (base_name,
                                                    base_name.upper()),
        "namespace": "example-com",
        "parameters": {
            "InstanceType": "m3.medium",
            "AZCount": 2,
        },
        "requires": []
    }
    definition.update(overrides)
    return definition
