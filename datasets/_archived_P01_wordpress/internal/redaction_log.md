# Redaction log: P01_wordpress
Every redaction made to docs_bundle/, so a reviewer can confirm nothing else was changed.

## content/en/docs/tutorials/stateful-application/mysql-wordpress-persistent-volume.md -> docs_bundle/README.md
- **Kubernetes-headed section**: `* Create PersistentVolumeClaims and PersistentVolumes * Create a `kustomization.yaml` with * a Secret generator * MySQL resource configs * WordPress resource configs * Apply the kustomization director`
- **Kubernetes-headed section**: `The `kustomization.yaml` contains all the resources for deploying a WordPress site and a MySQL database. You can apply the directory by ```shell kubectl apply -k ./ ``` Now you can verify that all obj`
- **Kubernetes-headed section**: `1. Run the following command to delete your Secret, Deployments, Services and PersistentVolumeClaims: ```shell kubectl delete -k ./ ````
