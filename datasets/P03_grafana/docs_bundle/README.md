---
aliases:
  - ../../installation/kubernetes/
description: Guide for deploying Grafana on Kubernetes
labels:
  products:
    - enterprise
    - oss
menuTitle: Grafana on Kubernetes
title: Deploy Grafana on Kubernetes
weight: 500
---

# Deploy Grafana on Kubernetes
[Kubernetes deployment instructions removed from this bundle]
## Before you begin

To follow this guide:

- You need the latest version of [Kubernetes](https://kubernetes.io/) running either locally or remotely on a public or private cloud.

- If you plan to use it in a local environment, you can use various Kubernetes options such as [minikube](https://minikube.sigs.k8s.io/docs/), [kind](https://kind.sigs.k8s.io/), [Docker Desktop](https://docs.docker.com/desktop/kubernetes/), and others.

- If you plan to use Kubernetes in a production setting, it's recommended to utilize managed cloud services like [Google Kubernetes Engine (GKE)](https://cloud.google.com/kubernetes-engine), [Amazon Elastic Kubernetes Service (EKS)](https://aws.amazon.com/eks/), or [Azure Kubernetes Service (AKS)](https://azure.microsoft.com/en-us/products/kubernetes-service/).

## System requirements

This section provides minimum hardware and software requirements.

### Minimum Hardware Requirements

- Disk space: 1 GB
- Memory: 750 MiB (approx 750 MB)
- CPU: 250m (approx 0.25 cores)

### Supported databases

For a list of supported databases, refer to [supported databases](/docs/grafana/latest/setup-grafana/installation#supported-databases).

### Supported web browsers

For a list of support web browsers, refer to [supported web browsers](/docs/grafana/latest/setup-grafana/installation#supported-web-browsers).

{{< admonition type="note" >}}
Enable port `3000` in your network environment, as this is the Grafana default port.
{{< /admonition >}}

## Deploy Grafana OSS on Kubernetes
[Kubernetes deployment instructions removed from this bundle]
## Access Grafana on Managed K8s Providers
[Kubernetes deployment instructions removed from this bundle]
## Access Grafana using minikube

There are multiple ways to access the Grafana UI on a web browser when using minikube. For more information about minikube, refer to [How to access applications running within minikube](https://minikube.sigs.k8s.io/docs/handbook/accessing/).

This section lists the two most common options for accessing an application running in minikube.

### Option 1: Expose the service

This option uses the `type: LoadBalancer` in the `grafana.yaml` service manifest, which makes the service accessible through the `minikube service` command. For more information, refer to [minikube Service command usage](https://minikube.sigs.k8s.io/docs/commands/service/).

1. Run the following command to obtain the Grafana service IP:

   ```bash
   minikube service grafana --namespace=my-grafana
   ```

   The output returns the Kubernetes URL for service in your local cluster.

   ```bash
   |------------|---------|-------------|------------------------------|
   | NAMESPACE  |  NAME   | TARGET PORT |             URL              |
   |------------|---------|-------------|------------------------------|
   | my-grafana | grafana |        3000 | http://192.168.122.144:32182 |
   |------------|---------|-------------|------------------------------|
   Opening service my-grafana/grafana in default browser...
   http://192.168.122.144:32182
   ```

1. Run a `curl` command to verify whether a given connection should work in a browser under ideal circumstances.

   ```bash
   curl 192.168.122.144:32182
   ```

   The following example output shows that an endpoint has been located:

   `<a href="/login">Found</a>.`

1. Access the Grafana UI in the browser using the provided IP:Port from the command above. For example `192.168.122.144:32182`

   The Grafana sign-in page appears.

1. To sign in to Grafana, enter `admin` for both the username and password.

### Option 2: Use port forwarding
[Kubernetes deployment instructions removed from this bundle]
## Update an existing deployment using a rolling update strategy
[Kubernetes deployment instructions removed from this bundle]
### Change Grafana image version
[Kubernetes deployment instructions removed from this bundle]
### Roll back a deployment
[Kubernetes deployment instructions removed from this bundle]
## Provision Grafana resources using configuration files
[Kubernetes deployment instructions removed from this bundle]
## Troubleshooting

This section includes troubleshooting tips you might find helpful when deploying Grafana on Kubernetes.

### Collecting logs

It is important to view the Grafana server logs while troubleshooting any issues.

1. To check the Grafana logs, run the following command:

   ```bash
   # dump Pod logs for a Deployment (single-container case)
   kubectl logs --namespace=my-grafana deploy/grafana
   ```

1. If you have multiple containers running in the deployment, run the following command to obtain the logs only for the Grafana deployment:

   ```bash
   # dump Pod logs for a Deployment (multi-container case)
   kubectl logs --namespace=my-grafana deploy/grafana -c grafana
   ```

For more information about accessing Kubernetes application logs, refer to [Pods](https://kubernetes.io/docs/reference/kubectl/cheatsheet/#interacting-with-running-pods) and [Deployments](https://kubernetes.io/docs/reference/kubectl/cheatsheet/#interacting-with-deployments-and-services).

### Increasing log levels to debug mode
[Kubernetes deployment instructions removed from this bundle]
### Using the --dry-run command
[Kubernetes deployment instructions removed from this bundle]
## Remove Grafana
[Kubernetes deployment instructions removed from this bundle]
## Deploy Grafana Enterprise on Kubernetes
[Kubernetes deployment instructions removed from this bundle]
### Obtain Grafana Enterprise license

To run Grafana Enterprise, you need a valid license.
To obtain a license, [contact a Grafana Labs representative](/contact?about=grafana-enterprise).
This topic assumes that you have a valid license in a `license.jwt` file.
Associate your license with a URL that you can use later in the topic.

### Create license secret
[Kubernetes deployment instructions removed from this bundle]
### Create Grafana Enterprise configuration

1. Create a Grafana configuration file with the name `grafana.ini`

1. Paste the following YAML contents into the file you created:

   ```yaml
   [enterprise]
   license_path = /etc/grafana/license/license.jwt
   [server]
   root_url =/your/license/root/url
   ```

1. Update the `root_url` field to the url associated with the license provided to you.

### Create Configmap for Grafana Enterprise configuration
[Kubernetes deployment instructions removed from this bundle]
### Create Grafana Enterprise Kubernetes manifest
[Kubernetes deployment instructions removed from this bundle]