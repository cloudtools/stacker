package stacker

import (
	"errors"
	"fmt"
	"log"
	"strings"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/cloudformation"
	"github.com/mgutz/ansi"
	"github.com/remind101/stacker/dag"
)

const Version = "0.0.1"

// Stacker is the primary interface.
type Stacker struct {
	StackBuilder
}

// New returns a new Stacker instance that will use p to provision
// CloudFormation stacks.
func New(b StackBuilder) *Stacker {
	return &Stacker{StackBuilder: b}
}

// NewDefault returns a new Stacker instance that uses a default configured
// CloudFormation API client.
func NewDefault() *Stacker {
	c := cloudformation.New(session.New())
	return New(WithLogging(NewCloudFormationStackBuilder(c)))
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

		for _, p := range stack.Parameters {
			if p.Ref != nil && p.Value == "" {
				dep := plan.metaStack.Stack(p.Ref.Stack)
				value, ok := dep.outputs[p.Ref.Output]
				if !ok {
					panic(fmt.Sprintf("%s has no output %s", dep, p.Ref.Output))
				}
				p.Value = value
			}
		}

		var (
			outputs map[string]string
			err     error
		)

		if s.StackBuilder.Exists(stack) {
			outputs, err = s.StackBuilder.Update(stack)
		} else {
			outputs, err = s.StackBuilder.Create(stack)
		}

		if err == ErrNoUpdates {
			err = nil
		}

		if err != nil {
			return err
		}

		stack.outputs = outputs
		stack.visited = true
		return nil
	})
}

var ErrNoUpdates = errors.New("stack: no updates necessary")

// StackBuilder is an interface that can be implemented to create/update
// CloudFormation stacks.
type StackBuilder interface {
	Exists(*Stack) bool
	Update(*Stack) (outputs map[string]string, err error)
	Create(*Stack) (outputs map[string]string, err error)
}

type loggingStackBuilder struct {
	StackBuilder
}

func WithLogging(b StackBuilder) StackBuilder {
	return &loggingStackBuilder{b}
}

func (b *loggingStackBuilder) Create(stack *Stack) (map[string]string, error) {
	b.log(stack, "Creating stack...")
	return b.StackBuilder.Create(stack)
}

func (b *loggingStackBuilder) Update(stack *Stack) (map[string]string, error) {
	b.log(stack, "Updating stack...")
	return b.StackBuilder.Update(stack)
}

func (b *loggingStackBuilder) log(stack *Stack, msg string) {
	prefix := ansi.Color(fmt.Sprintf("[%s]", stack), "green+b")
	log.Println(prefix, msg)
}

// CloudFormationStackBuilder is an implementation of the StackBuilder interface
// that uses the CloudFormation API to build stacks.
type CloudFormationStackBuilder struct {
	cloudformation *cloudformation.CloudFormation
}

func NewCloudFormationStackBuilder(c *cloudformation.CloudFormation) *CloudFormationStackBuilder {
	return &CloudFormationStackBuilder{
		cloudformation: c,
	}
}

func (b *CloudFormationStackBuilder) Exists(stack *Stack) bool {
	_, err := b.cloudformation.DescribeStacks(&cloudformation.DescribeStacksInput{
		StackName: aws.String(stack.Name),
	})
	if err != nil {
		return false
	}
	return true
}

func (b *CloudFormationStackBuilder) params(stack *Stack) []*cloudformation.Parameter {
	var params []*cloudformation.Parameter
	for _, p := range stack.Parameters {
		params = append(params, &cloudformation.Parameter{
			ParameterKey:   aws.String(p.Name),
			ParameterValue: aws.String(p.Value),
		})
	}
	return params
}

func (b *CloudFormationStackBuilder) Update(stack *Stack) (map[string]string, error) {
	_, err := b.cloudformation.UpdateStack(&cloudformation.UpdateStackInput{
		StackName:    aws.String(stack.Name),
		Parameters:   b.params(stack),
		TemplateBody: aws.String(stack.Template),
	})
	if err != nil {
		if strings.Contains(err.Error(), "ValidationError: No updates are to be performed") {
			outputs, err := b.outputs(stack)
			if err != nil {
				return outputs, err
			}
			return outputs, ErrNoUpdates
		}

		return nil, err
	}
	if err := b.cloudformation.WaitUntilStackUpdateComplete(&cloudformation.DescribeStacksInput{
		StackName: aws.String(stack.Name),
	}); err != nil {
		return nil, err
	}

	return b.outputs(stack)
}

func (b *CloudFormationStackBuilder) Create(stack *Stack) (map[string]string, error) {
	_, err := b.cloudformation.CreateStack(&cloudformation.CreateStackInput{
		StackName:    aws.String(stack.Name),
		Parameters:   b.params(stack),
		TemplateBody: aws.String(stack.Template),
	})
	if err != nil {
		return nil, err
	}

	if err := b.cloudformation.WaitUntilStackCreateComplete(&cloudformation.DescribeStacksInput{
		StackName: aws.String(stack.Name),
	}); err != nil {
		return nil, err
	}

	return b.outputs(stack)
}

func (b *CloudFormationStackBuilder) outputs(stack *Stack) (map[string]string, error) {
	resp, err := b.cloudformation.DescribeStacks(&cloudformation.DescribeStacksInput{
		StackName: aws.String(stack.Name),
	})
	if err != nil {
		return nil, err
	}

	if len(resp.Stacks) != 1 {
		return nil, errors.New("expected 1 stack to be described")
	}

	outputs := make(map[string]string)
	for _, output := range resp.Stacks[0].Outputs {
		outputs[*output.OutputKey] = *output.OutputValue
	}

	return outputs, nil
}
