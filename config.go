package stacker

import (
	"io"
	"io/ioutil"

	"gopkg.in/yaml.v2"
)

// Config represents the yaml configuration for defining a metastack.
type Config struct {
	Stacks []struct {
		Name       string            `yaml:"name"`
		Template   string            `yaml:"template"`
		Parameters map[string]string `yaml:"parameters"`
	} `yaml:"stacks"`
}

// Parse parses a YAML formatted config into a MetaStack.
func Parse(r io.Reader) (*MetaStack, error) {
	var config Config
	raw, err := ioutil.ReadAll(r)
	if err != nil {
		return nil, err
	}
	yaml.Unmarshal(raw, &config)
	var m MetaStack
	for _, stack := range config.Stacks {
		m.Stacks = append(m.Stacks, &Stack{
			Name:       stack.Name,
			Template:   stack.Template,
			Parameters: stack.Parameters,
		})
	}
	return &m, nil
}
