# 'production' Empire example

This is meant to be a base guideline for building a production ready
[Empire][Empire] cluster. In order to launch it, you'll want to modify the
[example.env][example.env] to fit your needs. It's worth reading through the
[example.env][example.env] & [empire.yaml][empire.yaml] for the comments that
detail how things will be built. Once the env is to your liking, you can launch
the environment by running the following command:

```
stacker -e conf/empire/example.env -r <region> <namespace> conf/empire/empire.yaml

# Example:
stacker -e conf/empire/example.env -r us-east-1 my-unique-namespace conf/empire/empire.yaml
```

Right now it takes around 20-30 minutes to finish bringing up the entire
environment due largely to how long it takes RDS to build the Empire database.

Rather than use the ECS Container AMI that Amazon provides, the Empire team
has built their own [Empire AMI][empire_ami] based on Ubuntu 14.04.

# Security

These blueprints & stack definitions assume a base level of security, but could
likely be tightened up quite a bit more to suit your needs. Some basics:

- SSL on the Empire API ELB
- All hosts except NAT & bastion hosts in private subnets with no public
  addresses
- Bastion hosts (ssh) and Empire API ELB (https) access are firewalled to a
  single trusted CIDR range
- Empire Minions & Controllers have no direct network access to each other
- The Empire database is in the private VPC and can only be accessed by the
  Empire Controller hosts.
- Github authentication is setup on the Empire API (provided you give all of
  the necessary variables for github in the environment)

That said - if you see something that we missed, please let me know!

[Empire]: https://github.com/remind101/empire/
[example.env]: https://github.com/remind101/stacker/blob/master/conf/empire/example.env
[empire.yaml]: https://github.com/remind101/stacker/blob/master/conf/empire/empire.yaml
[empire_ami]: https://github.com/remind101/empire_ami
