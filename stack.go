package stacker

import (
	"fmt"
	"strings"

	"github.com/remind101/stacker/dag"
)

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

// Stack represents a single cloudformation stack and it's dependencies.
type Stack struct {
	// Name of the stack
	Name string

	// The CloudFormation template json.
	Template string

	// Parameters to apply.
	Parameters map[string]string

	// outputs from the stack. This is only populated after the stack is
	// updated or created.
	outputs map[string]string

	// Set to true when this stack is created/updated.
	visited bool
}

func (s *Stack) String() string {
	return s.Name
}

// Compile takes a MetaStack and compiles it into a dependency tree.
func Compile(metaStack *MetaStack) (*Plan, error) {
	var plan Plan
	plan.graph.Add(metaStack)
	for _, stack := range metaStack.Stacks {
		plan.graph.Add(stack)
		plan.graph.Connect(dag.BasicEdge(metaStack, stack))
	}

	for _, stack := range metaStack.Stacks {
		for _, value := range stack.Parameters {
			if strings.Contains(value, "::") {
				parts := strings.Split(value, "::")
				dep := metaStack.Stack(parts[0])
				if dep == nil {
					panic(fmt.Sprintf("%s not found in stack", parts[0]))
				}
				plan.graph.Connect(dag.BasicEdge(stack, dep))
			}
		}
	}

	return &plan, plan.Validate()
}
