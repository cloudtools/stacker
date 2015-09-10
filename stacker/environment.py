

def parse_environment(raw_environment):
    environment = {}
    for line in raw_environment.split('\n'):
        if ':' not in line:
            continue

        key, value = line.split(':', 1)
        environment[key] = value.strip()
    return environment
