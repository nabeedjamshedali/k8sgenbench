---
title: In-cluster
sidebar_position: 1
---

A common use case for any Kubernetes web UI is to deploy it in-cluster and
set up an ingress server for having it available to users.

## Using Helm

The easiest way to install headlamp in your existing cluster is to
use [helm](https://helm.sh/docs/intro/quickstart/) with our [helm chart](https://github.com/kubernetes-sigs/headlamp/tree/main/charts/headlamp).

```bash
# first add our custom repo to your local helm repositories
helm repo add headlamp https://kubernetes-sigs.github.io/headlamp/

# now you should be able to install headlamp via helm
helm install my-headlamp headlamp/headlamp --namespace kube-system
```

As usual, it is possible to configure the helm release via the [values file](https://github.com/kubernetes-sigs/headlamp/blob/main/charts/headlamp/values.yaml) or setting your preferred values directly.

```bash
# install headlamp with your own values.yaml
helm install my-headlamp headlamp/headlamp --namespace kube-system -f values.yaml

# install headlamp by setting your values directly
helm install my-headlamp headlamp/headlamp --namespace kube-system --set replicaCount=2
```

### Cluster Inventory

Headlamp can discover clusters from Cluster Inventory API `ClusterProfile`
resources when Cluster Inventory is enabled. The Helm chart configures the
backend flags from `config.clusterInventory` and mounts an access provider
config file.

Create `cluster-inventory-values.yaml`:

```yaml
[Kubernetes manifest removed from this bundle]
```

Then install Headlamp with the values file:

```bash
helm install my-headlamp headlamp/headlamp --namespace kube-system --values cluster-inventory-values.yaml
```

The `accessProvidersConfig` object is the provider config consumed by the
Cluster Inventory access provider. The `plugins` entries are Kubernetes `image`
volumes that mount provider binaries into the Headlamp container, not Headlamp
UI plugins. By default, Headlamp watches `ClusterProfile` resources that do not
have the `headlamp.dev/ignore` label because the chart sets
`config.clusterInventory.labelSelector` to `!headlamp.dev/ignore`. Discovery is
scoped to the Headlamp pod's namespace. This follows the namespaced consumer
model for ClusterProfile: each Headlamp instance reads the profiles published
for that consumer's namespace.

To watch specific namespaces, set:

```yaml
config:
  clusterInventory:
    namespaces:
      - inventory-team-a
      - inventory-team-b
```

Each selected namespace requires permission to get, list, and watch
ClusterProfiles. Set `namespaces` to `["*"]` to watch all namespaces. `*`
cannot be combined with named namespaces, and all-namespace discovery requires
equivalent cluster-wide access.

## Using simple yaml
[Kubernetes deployment instructions removed from this bundle]
## Optional TLS Backend Termination

Headlamp supports optional TLS termination at the backend server. The default is to terminate at the ingress (default) or optionally directly at the Headlamp container. This enables use cases such as NGINX TLS passthrough and transport server. See [tls](./tls.md) for details and usage.

## Use a non-default kube config file
[Kubernetes deployment instructions removed from this bundle]
### Option 1: Mount the kubeconfig at the default location

Headlamp loads a kubeconfig file from
`/home/headlamp/.config/Headlamp/kubeconfigs/config` at startup. Mount the
Secret at that directory with these Helm values (the key inside the Secret
must be named `config`):

```yaml
volumeMounts:
  - name: kubeconfig
    mountPath: /home/headlamp/.config/Headlamp/kubeconfigs
    readOnly: true
volumes:
  - name: kubeconfig
    secret:
      secretName: headlamp-kubeconfig
```

```bash
helm install my-headlamp headlamp/headlamp --namespace kube-system -f values.yaml
```

### Option 2: Mount the kubeconfig anywhere and use the -kubeconfig argument

If you prefer an explicit path, mount the Secret wherever you like and pass
the path with the `-kubeconfig` argument through `config.extraArgs`:

```yaml
config:
  extraArgs:
    - -kubeconfig=/headlamp/kubeconfig/config
volumeMounts:
  - name: kubeconfig
    mountPath: /headlamp/kubeconfig
    readOnly: true
volumes:
  - name: kubeconfig
    secret:
      secretName: headlamp-kubeconfig
```

### Use several kubeconfig files
[Kubernetes deployment instructions removed from this bundle]
### Using plain YAML instead of Helm

If you deploy Headlamp with a plain manifest (like
[kubernetes-headlamp.yaml](https://github.com/kubernetes-sigs/headlamp/blob/main/kubernetes-headlamp.yaml)),
apply the same idea directly on the Deployment:

```yaml
spec:
  template:
    spec:
      containers:
        - name: headlamp
          image: ghcr.io/headlamp-k8s/headlamp:latest
          args:
            - "-in-cluster"
            - "-plugins-dir=/headlamp/plugins"
            - "-kubeconfig=/headlamp/kubeconfig/config"
          volumeMounts:
            - name: kubeconfig
              mountPath: /headlamp/kubeconfig
              readOnly: true
      volumes:
        - name: kubeconfig
          secret:
            secretName: headlamp-kubeconfig
```

## Exposing Headlamp with an ingress server
[Kubernetes deployment instructions removed from this bundle]
## Exposing Headlamp with port-forwarding

If you want to quickly access Headlamp (after having its service running) and
don't want to set up an ingress for it, you can run use port-forwarding as follows:

```bash
kubectl port-forward -n kube-system service/headlamp 8080:80
```

and then you can access `localhost:8080` in your browser.

## Accessing Headlamp

Once Headlamp is up and running, be sure to enable access to it either by creating
a [service account](../#create-a-service-account-token) or by setting up
[OIDC](./oidc).

## Plugin Management

Headlamp supports managing plugins through a sidecar container when deployed in-cluster.

### Using values.yaml

You can directly specify the plugin configuration in your `values.yaml`:

```yaml
config:
  watchPlugins: true
pluginsManager:
  enabled: true
  configContent: |
    plugins:
      - name: my-plugin
        source: https://artifacthub.io/packages/headlamp/my-repo/my_plugin
        version: 1.0.0
    installOptions:
      parallel: true
      maxConcurrent: 2
  baseImage: node:lts-alpine
  version: latest
```

### Using a Separate plugin.yml

Alternatively, you can maintain a separate `plugin.yml` file:

1. Create a `plugin.yml` file:
```yaml
plugins:
  - name: my-plugin
    source: https://artifacthub.io/packages/headlamp/my-repo/my_plugin
    version: 1.0.0
    # Optional: specify dependencies if needed
    dependencies:
      - another-plugin

installOptions:
  parallel: true
  maxConcurrent: 2
```

2. Install/upgrade Headlamp using the plugin configuration:
```bash
helm upgrade --install my-headlamp headlamp/headlamp --namespace kube-system -f values.yaml --set pluginsManager.configContent="$(cat plugin.yml)"
```

### Plugin Configuration Format

The plugin configuration supports the following fields:

- `plugins`: Array of plugins to install
  - `name`: Plugin name (required)
  - `source`: Plugin source URL from Artifact Hub (required)
  - `version`: Plugin version (required)
  - `dependencies`: Array of plugin names that this plugin depends on (optional)
- `installOptions`:
  - `parallel`: Whether to install plugins in parallel (default: false)
  - `maxConcurrent`: Maximum number of concurrent installations when parallel is true

### Auto-updating Plugins

Headlamp's plugin manager can automatically watch for changes in the plugin configuration. However, you need to enable watch for these changes in the main headlamp container. This can be enabled through the `watchPlugins` setting in `values.yaml`:

```yaml
config:
  watchPlugins: true  # Set to true to enable automatic plugin updates in main headlamp container
```

When enabled, any plugins' changes (either through Helm upgrades or direct ConfigMap updates) wil update in the main headlamp container by enabling --watch-plugins-changes flag on headlamp server.
