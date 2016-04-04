package stacker

import "github.com/remind101/stacker/dag"

// StackProvisioner is an interface that can be implemented to create/update
// CloudFormation stacks.
type StackProvisioner interface {
	Provision(*Stack) (outputs map[string]string, err error)
}

// Stacker is the primary interface.
type Stacker struct {
	StackProvisioner
}

// New returns a new Stacker instance that will use p to provision
// CloudFormation stacks.
func New(p StackProvisioner) *Stacker {
	return &Stacker{StackProvisioner: p}
}

// Executes walks through each stack and creates it or updates it.
func (s *Stacker) Execute(plan *Plan) error {
	return plan.graph.Walk(func(v dag.Vertex) error {
		if _, ok := v.(*MetaStack); ok {
			return nil
		}

		stack := v.(*Stack)
		if stack.visited {
			return nil
		}
		outputs, err := s.StackProvisioner.Provision(stack)
		if err != nil {
			return err
		}
		stack.outputs = outputs
		stack.visited = true
		return nil
	})
}
