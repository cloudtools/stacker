

def parse_environment(raw_environment):
    environment = {}
    for line in raw_environment.split('\n'):
        line = line.strip()

        if ':' not in line:
            continue

        if line.startswith('#'):
            continue

        key, value = line.split(':', 1)
        environment[key] = value.strip()
    return environment
