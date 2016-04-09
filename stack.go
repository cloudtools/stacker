package stacker

import "strings"

// MetaStack represents the combined list of stacks.
type MetaStack struct {
	Stacks []*Stack
}

// Returns the Stack with the given name, or nil if it doesn't exist.
func (s *MetaStack) Stack(name string) *Stack {
	for _, stack := range s.Stacks {
		if stack.Name == name {
			return stack
		}
	}

	return nil
}

// Returns the string representation of this MetaStack.
func (s *MetaStack) String() string {
	return "(root)"
}

type Ref struct {
	Stack  string
	Output string
}

// Parameter represents a parameter to a Stack.
type Parameter struct {
	// The name of the parameter.
	Name string

	// The value of the parameter.
	Value string

	// If provided, the output from a different stack
	Ref *Ref
}

// newParameter returns a new Parameter instance.
func newParameter(name, value string) (p Parameter) {
	p.Name = name

	if strings.Contains(value, "::") {
		parts := strings.Split(value, "::")
		p.Ref = &Ref{
			Stack:  parts[0],
			Output: parts[1],
		}
	} else {
		p.Value = value
	}

	return
}

// Stack represents a single cloudformation stack and it's dependencies.
type Stack struct {
	// Name of the stack
	Name string

	// The CloudFormation template json.
	Template string

	// Parameters to apply.
	Parameters []Parameter

	// outputs from the stack. This is only populated after the stack is
	// updated or created.
	outputs map[string]string

	// Set to true when this stack is created/updated.
	visited bool
}

func (s *Stack) String() string {
	return s.Name
}
