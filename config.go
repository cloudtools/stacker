package stacker

import (
	"encoding/json"
	"io"
	"io/ioutil"
)

// Config represents the json configuration for defining a metastack.
type Config struct {
	Stacks []struct {
		Name       string                 `json:"Name"`
		Template   map[string]interface{} `json:"Template"`
		Parameters map[string]string      `json:"Parameters"`
	} `json:"Stacks"`
}

// Parse parses a YAML formatted config into a MetaStack.
func Parse(r io.Reader) (*MetaStack, error) {
	var config Config
	raw, err := ioutil.ReadAll(r)
	if err != nil {
		return nil, err
	}
	json.Unmarshal(raw, &config)
	var m MetaStack
	for _, stack := range config.Stacks {
		raw, err := jsonTemplate(stack.Template)
		if err != nil {
			return nil, err
		}
		template := string(raw)
		m.Stacks = append(m.Stacks, &Stack{
			Name:       stack.Name,
			Template:   template,
			Parameters: stack.Parameters,
		})
	}
	return &m, nil
}

func jsonTemplate(m map[string]interface{}) ([]byte, error) {
	return json.Marshal(jsonYaml(m))
}

func jsonYaml(m map[string]interface{}) map[string]interface{} {
	var coerce func(interface{}) interface{}
	coerce = func(v interface{}) interface{} {
		switch v := v.(type) {
		case map[interface{}]interface{}:
			coerced := make(map[string]interface{})
			for key, val := range v {
				coerced[key.(string)] = coerce(val)
			}
			return coerced
		default:
			return v
		}
	}
	safe := make(map[string]interface{})
	for k, v := range m {
		safe[k] = coerce(v)
	}
	return safe
}
