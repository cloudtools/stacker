def mock_hook(provider, context, **kwargs):
    return {"result": kwargs["value"]}
