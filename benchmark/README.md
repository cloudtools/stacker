This is a stacker config for benchmarking stackers performance, you can run it with:

```
$ cp benchmark.env.example benchmark.env # change the namespace
$ time stacker build benchmark.env benchmark.yaml
```

When you're done:

```
$ stacker destroy --force benchmark.env benchmark.yaml
```
