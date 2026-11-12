# Redaction log: P03_grafana
Every redaction made to docs_bundle/, so a reviewer can confirm nothing else was changed.

## docs/sources/setup-grafana/installation/kubernetes/index.md -> docs_bundle/README.md
- **Kubernetes-headed section**: `On this page, you will find instructions for installing and running Grafana on Kubernetes using Kubernetes manifests for the setup. If Helm is your preferred option, refer to [Grafana Helm community c`
- **Kubernetes-headed section**: `This section explains how to install Grafana OSS using Kubernetes. {{< admonition type="note" >}} If you want to install Grafana Enterprise on Kubernetes, refer to [Deploy Grafana Enterprise on Kubern`
- **Kubernetes-headed section**: `In this task, you access Grafana deployed on a Managed Kubernetes provider using a web browser. Accessing Grafana via a web browser is straightforward if it is deployed on a Managed Kubernetes Provide`
- **Kubernetes-headed section**: `If Option 1 does not work in your minikube environment (this mostly depends on the network), then as an alternative you can use the port forwarding option for the Grafana service on port `3000`. For m`
- **Kubernetes-headed section**: `Rolling updates enable deployment updates to take place with no downtime by incrementally updating Pods instances with new ones. The new Pods will be scheduled on nodes with available resources. For m`
- **Kubernetes-headed section**: `1. To change the deployed Grafana version, run the following `kubectl edit` command: ```bash kubectl edit deployment grafana --namespace=my-grafana ``` 1. In the editor, change the container image und`
- **Kubernetes-headed section**: `When the Grafana deployment becomes unstable due to crash looping, bugs, and so on, you can roll back a deployment to an earlier version (a `REVISION`). By default, Kubernetes deployment rollout histo`
- **Kubernetes-headed section**: `Provisioning can add, update, or delete resources specified in your configuration files when Grafana starts. For detailed information, refer to [Grafana Provisioning](/docs/grafana/<GRAFANA_VERSION>/a`
- **Kubernetes-headed section**: `By default, the Grafana log level is set to `info`, but you can increase it to `debug` mode to fetch information needed to diagnose and troubleshoot a problem. For more information about Grafana log l`
- **Kubernetes-headed section**: `You can use the Kubernetes `--dry-run` command to send requests to modifying endpoints and determine if the request would have succeeded. Performing a dry run can be useful for catching errors or unin`
- **Kubernetes-headed section**: `If you want to remove any of the Grafana deployment objects, use the `kubectl delete command`. 1. If you want to remove the complete Grafana deployment, run the following command: ```bash kubectl dele`
- **Kubernetes-headed section**: `The process for deploying Grafana Enterprise is almost identical to the preceding process, except for additional steps that are required for adding your license file.`
- **Kubernetes-headed section**: `Create a Kubernetes secret from your license file using the following command: ```bash kubectl create secret generic ge-license --from-file=/path/to/your/license.jwt ````
- **Kubernetes-headed section**: `Create a Kubernetes Configmap from your `grafana.ini` file with the following command: ```bash kubectl create configmap ge-config --from-file=/path/to/your/grafana.ini ````
- **Kubernetes-headed section**: `1. Create a `grafana.yaml` file, and copy-and-paste the following content into it. The following YAML is identical to the one for a Grafana installation, except for the additional references to the Co`

## conf/defaults.ini -> docs_bundle/defaults.ini
- **Kubernetes-headed section**: `workload_identity_tenant_id =`
- **Kubernetes-headed section**: `workload_identity_client_id =`

## Dockerfile -> docs_bundle/Dockerfile
- no redactions
