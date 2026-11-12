---
title: "Example: Deploying WordPress and MySQL with Persistent Volumes"
reviewers:
- ahmetb
content_type: tutorial
weight: 20
card: 
  name: tutorials
  weight: 40
  title: "Stateful Example: Wordpress with Persistent Volumes"
---

<!-- overview -->
This tutorial shows you how to deploy a WordPress site and a MySQL database using
Minikube. Both applications use PersistentVolumes and PersistentVolumeClaims to store data.

A [PersistentVolume](/docs/concepts/storage/persistent-volumes/) (PV) is a piece
of storage in the cluster that has been manually provisioned by an administrator,
or dynamically provisioned by Kubernetes using a [StorageClass](/docs/concepts/storage/storage-classes).
A [PersistentVolumeClaim](/docs/concepts/storage/persistent-volumes/#persistentvolumeclaims) (PVC)
is a request for storage by a user that can be fulfilled by a PV. PersistentVolumes and
PersistentVolumeClaims are independent from Pod lifecycles and preserve data through
restarting, rescheduling, and even deleting Pods.

{{< alert color="danger" title="Warning" >}}
This deployment is not suitable for production use cases, as it uses single instance
WordPress and MySQL Pods. Consider using
[WordPress Helm Chart](https://github.com/bitnami/charts/tree/master/bitnami/wordpress)
to deploy WordPress in production.
{{< /alert >}}

{{< alert color="info" title="Note" >}}
The files provided in this tutorial are using GA Deployment APIs and are specific
to kubernetes version 1.9 and later. If you wish to use this tutorial with an earlier
version of Kubernetes, please update the API version appropriately, or reference
earlier versions of this tutorial.
{{< /alert >}}

## {{% heading "objectives" %}}
[Kubernetes deployment instructions removed from this bundle]
## {{% heading "prerequisites" %}}

{{< include "task-tutorial-prereqs.md" >}} {{< version-check >}}

The example shown on this page works with `kubectl` 1.27 and above.

Download the following configuration files:

1. [mysql-deployment.yaml](/examples/application/wordpress/mysql-deployment.yaml)

1. [wordpress-deployment.yaml](/examples/application/wordpress/wordpress-deployment.yaml)

<!-- lessoncontent -->

## Create PersistentVolumeClaims and PersistentVolumes

MySQL and Wordpress each require a PersistentVolume to store data.
Their PersistentVolumeClaims will be created at the deployment step.

Many cluster environments have a default StorageClass installed.
When a StorageClass is not specified in the PersistentVolumeClaim,
the cluster's default StorageClass is used instead.

When a PersistentVolumeClaim is created, a PersistentVolume is dynamically
provisioned based on the StorageClass configuration.

{{< alert color="danger" title="Warning" >}}
In local clusters, the default StorageClass uses the `hostPath` provisioner.
`hostPath` volumes are only suitable for development and testing. With `hostPath`
volumes, your data lives in `/tmp` on the node the Pod is scheduled onto and does
not move between nodes. If a Pod dies and gets scheduled to another node in the
cluster, or the node is rebooted, the data is lost.
{{< /alert >}}

{{< alert color="info" title="Note" >}}
If you are bringing up a cluster that needs to use the `hostPath` provisioner,
the `--enable-hostpath-provisioner` flag must be set in the `controller-manager` component.
{{< /alert >}}

{{< alert color="info" title="Note" >}}
If you have a Kubernetes cluster running on Google Kubernetes Engine, please
follow [this guide](https://cloud.google.com/kubernetes-engine/docs/tutorials/persistent-disk).
{{< /alert >}}

## Create a kustomization.yaml

### Add a Secret generator

A [Secret](/docs/concepts/configuration/secret/) is an object that stores a piece
of sensitive data like a password or key. Since 1.14, `kubectl` supports the
management of Kubernetes objects using a kustomization file. You can create a Secret
by generators in `kustomization.yaml`.

Add a Secret generator in `kustomization.yaml` from the following command.
You will need to replace `YOUR_PASSWORD` with the password you want to use.

```shell
cat <<EOF >./kustomization.yaml
secretGenerator:
- name: mysql-pass
  literals:
  - password=YOUR_PASSWORD
EOF
```

## Add resource configs for MySQL and WordPress

The following manifest describes a single-instance MySQL Deployment. The MySQL
container mounts the PersistentVolume at /var/lib/mysql. The `MYSQL_ROOT_PASSWORD`
environment variable sets the database password from the Secret.

{{% code_sample file="application/wordpress/mysql-deployment.yaml" %}}

The following manifest describes a single-instance WordPress Deployment. The WordPress container mounts the
PersistentVolume at `/var/www/html` for website data files. The `WORDPRESS_DB_HOST` environment variable sets
the name of the MySQL Service defined above, and WordPress will access the database by Service. The
`WORDPRESS_DB_PASSWORD` environment variable sets the database password from the Secret kustomize generated.

{{% code_sample file="application/wordpress/wordpress-deployment.yaml" %}}

1. Download the MySQL deployment configuration file.

   ```shell
   curl -LO https://k8s.io/examples/application/wordpress/mysql-deployment.yaml
   ```

2. Download the WordPress configuration file.

   ```shell
   curl -LO https://k8s.io/examples/application/wordpress/wordpress-deployment.yaml
   ```

3. Add them to `kustomization.yaml` file.

   ```shell
   cat <<EOF >>./kustomization.yaml
   resources:
     - mysql-deployment.yaml
     - wordpress-deployment.yaml
   EOF
   ```

## Apply and Verify
[Kubernetes deployment instructions removed from this bundle]
## {{% heading "cleanup" %}}
[Kubernetes deployment instructions removed from this bundle]
## {{% heading "whatsnext" %}}

* Learn more about [Introspection and Debugging](/docs/tasks/debug/debug-application/debug-running-pod/)
* Learn more about [Jobs](/docs/concepts/workloads/controllers/job/)
* Learn more about [Port Forwarding](/docs/tasks/access-application-cluster/port-forward-access-application-cluster/)
* Learn how to [Get a Shell to a Container](/docs/tasks/debug/debug-application/get-shell-running-container/)
