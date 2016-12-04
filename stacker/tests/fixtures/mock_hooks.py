def mock_hook(region, namespace, mappings, parameters, **kwargs):
    return {"result": kwargs["value"]}
