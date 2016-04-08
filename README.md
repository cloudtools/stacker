# Stacker

This is a Go rewrite of stacker.

## Usage

Stacker revolves around the idea of a compiled "meta" template, that includes multiple CloudFormation stacks that depend on each other. Child stacks can use the outputs defined in a parent stack as input parameters. For example, you might define a "vpc" stack that has an output with the Vpc ID, then define a "bastion" stack that uses the Vpc ID is an input parameter.

## Goals

* Use a true dependency graph (directed acyclic graph), because:
  * It detects cyclic dependencies.
  * It makes it easy to parallelize.
  * It makes doing partial stack updates easy (walk back through the dependency graph to make sure all deps are updated)
* Support CloudFormation changesets.
* Support non-troposphere stack definitions (define stacks however you like).
  * Support plugins for defining stacks (e.g. python, json, yaml, whatever)
* Reach feature parity with the Python version.

## Non goals

* Be completely backwards compatible with Stacker 0.x.

## Maybe Goals

* Support an API (e.g. POST a tarball, stacker provisions it)
